import contextlib
import io
import json
import os
import re
import subprocess
import sys
import uuid

import click
import inquirer

from sqlalchemy import create_engine

json_file_path = "data.json"

distros = {
    'ubuntu22.04': ["docker.io/library/ubuntu:22.04", "apt install {}"],
    'ubuntu20.04': ["docker.io/library/ubuntu:20.04", "apt install {}"],
    'fedora': ["docker.io/library/fedora:latest", "dnf install {}"],
    "debian": ["docker.io/library/debian:stable", "apt install {}"],
    'archlinux': ["docker.io/library/archlinux:latest", "pacman -Sy {}"],
    "kali": ["docker.io/kalilinux/kali-rolling", "apt install {}"],
    'leap': ["registry.opensuse.org/opensuse/tumbleweed:latest", "zypper install {}"],
    'alpine': ["docker.io/library/alpine:latest", "apk add {}"]
}

return_code = 0


def create_uuid(distro: str):
    return "vypper_managed_" + distro + "_" + str(uuid.uuid4().hex)[:4]


@click.group()
def cli():
    pass


def init_json():
    if not os.path.exists(json_file_path):
        with open("data.json", "w") as f:
            json.dump({
                "packages": {},
                "machines": {}
            }, f)


def load_json() -> dict:
    with open(json_file_path, "r") as f:
        new_data = json.load(f)
    return new_data


def dump_json(new_data: dict):
    with open(json_file_path, "w") as f:
        json.dump(new_data, f)


def find_container(distro: str):
    data = load_json()
    machines: dict = data["machines"]
    found = machines.get(distro, None)
    return found


def find_or_create_container(distro: str):
    data = load_json()
    machine = find_container(distro)
    if machine is None:
        machine = create_uuid(distro)
        setup_machine(distros[distro][0], machine, (distro == "archlinux"))
        data["machines"][distro] = machine
    dump_json(data)
    return machine


def setup_machine(image: str, name: str, install_yay=False):
    print("Pulling and creating the image, this may take some time...")
    with contextlib.redirect_stdout(io.BytesIO()):  # does not work
        os.system("distrobox create -i {} -n {}".format(image, name))
    print("Installing Base Packages, may also take a few minutes...")
    install_step = "echo 0"
    if install_yay:
        install_step = "sh -c \"pacman -S --needed --noconfirm git base-devel && git clone " \
                       "https://aur.archlinux.org/yay-bin.git " \
                       "&& cd yay-bin && makepkg --noconfirm -si\""
        print("I also need to install git.")
    with contextlib.redirect_stdout(io.BytesIO()):
        os.system("distrobox enter {} -- {}".format(name, install_step))


shorthands = {
    "Ubuntu 22.04": "ubuntu22.04",
    "Ubuntu 20.04": "ubuntu20.04",
    "Fedora": "fedora",
    "Arch Linux": "archlinux",
    "Arch Linux (AUR)": "archlinux",
    "Kali Linux": "kali",
    "OpenSUSE Leap": "leap",
    "Alpine": "alpine",
    "Debian": "debian"
}


def is_aur_command(a):
    return a == "Arch Linux (AUR)"


@click.command(name="dist-upgrade")
@click.argument("distro")
def dist_upgrade(distro):
    global return_code
    data = load_json()
    if distro:
        try:
            os.system("distrobox upgrade {}".format(data["machines"][distro]))
        except KeyError:
            click.echo("Distribution not installed via vypper.", err=True)
            return_code = 1
        return
    for i in data["machines"]:
        os.system("distrobox upgrade {}".format(data["machines"][i]))


@click.command()
@click.option("--distro", default="")
@click.option("--export-app", default=False)
@click.argument("target")
def install(distro, export_app, target: str):
    global return_code
    data = load_json()
    if os.system("sh -c command -v podman") == 0:
        backend = "podman"
    elif os.system("sh -c command -v docker") == 0:
        backend = "docker"
    else:
        click.echo("No Backend installed or not on PATH.")
        return_code = 127
        return
    if os.system("sh -c command -v distrobox") != 0:
        click.echo("Distrobox not installed or not on PATH.")
        return_code = 127
        return
    if target is None:
        click.echo("Please pass a file you want to install. See vypper install --help for more information.")
        return_code = 1
        return

    extension = os.path.splitext(target)[1]
    if extension == "":
        is_aur = False
        if distro == "":
            questions = [
                inquirer.List('distro',
                              message="On which distro do you want to install the package?",
                              choices=['Ubuntu 22.04', 'Ubuntu 20.04', 'Fedora', 'Arch Linux', "Arch Linux (AUR)",
                                       "Kali Linux", 'OpenSUSE Leap', "Debian", 'Alpine'],
                              ),
            ]
            answer = inquirer.prompt(questions)["distro"]
            image = shorthands[answer]
            is_aur = is_aur_command(answer)
        else:
            if distro not in shorthands.values():
                supported_distros = ""
                for i in shorthands.values():
                    supported_distros += i + " "
                click.echo("This distribution is not supported. Supported are: " + supported_distros)
                return_code = 1
                return
            image = distro
        container = find_or_create_container(image)
        command = distros[image][1].format(target)
        if is_aur:
            command = command.replace("pacman", "yay")
        else:
            command = "sudo " + command  # Yay does not need sudo
        os.system("distrobox enter {} -- {}".format(container, command))

        application_list = subprocess.run([backend, "exec", container, "sh -c \"ls /usr/share/applications ; ls "
                                                                       "/usr/local/share/applications  "
                                                                       "; ls /var/lib/flatpak/exports/share"
                                                                       "/applications\""],
                                          capture_output=True, text=True)
        possible_application = ""
        for i in application_list.stdout.split("\n"):
            if re.match(target, i, flags=re.IGNORECASE):
                possible_application = i
                break
        if not possible_application:
            application_list = subprocess.run([backend, "exec", container, "ls", "/usr/bin"], capture_output=True,
                                              text=True)
            # print(application_list.stdout)
            for i in application_list.stdout.split("\n"):
                if re.match(target, i, flags=re.IGNORECASE):
                    possible_application = os.path.join("/usr/bin/", i)
                    break
        if possible_application and (
                export_app or inquirer.confirm("Export {}?".format(possible_application))):
            sudo = ""
            if inquirer.confirm("Run always with sudo?"):
                sudo = "--sudo"
            if possible_application.startswith("/usr/bin"):
                os.system("distrobox enter {} -- {}".format(container, "distrobox-export --bin /usr/bin/{} {} "
                                                                       "--export-path ~/.local/bin".format(possible_application,
                                                                                                           sudo)))
                exported_binary="/usr/bin/"+possible_application
            else:
                os.system("distrobox enter {} -- {}".format(container, "distrobox-export --app {} {}".format(target,
                                                                                                             sudo)))
                exported_app=possible_application
        else:
            click.echo("Installation succeeded. Please run vypper export --help to find out how to access the installed"
                       " binaries or applications")

    elif extension.lower() == "deb":
        pass
    elif extension.lower() == "rpm":
        pass
    else:
        click.echo("This file type is not supported. Please open a Issue, if you want this to be accepted")
        return_code = 1
        return


# TODO: - Make output prettier
#       - Add export command
#       - Add remove command
#       - Add upgrade command
#       - Add documentation
#       - Add packages to the JSON File


cli.add_command(install)
cli.add_command(dist_upgrade)

if __name__ == "__main__":
    engine = create_engine("sqlite://db.sqlite", echo=True)
    if len(sys.argv) == 1:
        click.echo("ERROR: No Command given")
        sys.exit(1)
    cli()
    sys.exit(return_code)
