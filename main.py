import contextlib
import io
import uuid
import sys
import os
import click
import inquirer

image_installer = {
    "deb": {
        "Ubuntu 20.04": ["ubuntu:20.04", "apt"],
        "Ubuntu 22.04 (Recommended)": ["ubuntu:22.04", "apt"],
        "Debian": ["debian:stable", "apt"]
    },
    "rpm": {
        "OpenSUSE LEAP": ["registry.opensuse.org/opensuse/tumbleweed:latest", "zypper"],
        "Fedora (Recommended)": ["fedora:latest", "dnf"]
    }
}

distros = {
    'Ubuntu 22.04': ["ubuntu:22.04", "apt install {}"], 'Ubuntu 20.04': ["ubuntu:20.04", "apt install {}"],
    'Fedora': ["fedora:latest", "dnf install {}"], 'Arch Linux': ["archlinux:latest", "pacman -S {}"],
    'Arch Linux (AUR)': ["archlinux:latest", "sh -c \"pacman -Sy --noconfirm git; git clone "
                                             "https://aur.archlinux.org/{0}.git {0};"
                                             "cd {0}}; makepkg -si\""],
    'OpenSUSE Leap': ["registry.opensuse.org/opensuse/tumbleweed:latest", "zypper install {}"],
    'Alpine': ["alpine:latest", "apk add {}"]
}


def create_uuid():
    return "vypper_managed_" + uuid.uuid4().hex


@click.group()
def cli():
    pass


@click.command()
@click.option("--distro", default="")
@click.argument("target")
def install(distro, target: str):
    if os.system("sh -c command -v podman") == 0:
        backend = "podman"
    elif os.system("sh -c command -v docker") == 0:
        backend = "docker"
    else:
        click.echo("No Backend installed or not on PATH.")
        sys.exit(1)
    if os.system("sh -c command -v distrobox") != 0:
        click.echo("Distrobox not installed or not on PATH.")
        sys.exit(1)
    if target is None:
        click.echo("Please pass a file you want to install. See vypper install --help for more information.")
        sys.exit(1)

    extension = os.path.splitext(target)[1]
    if extension == "":
        questions = [
            inquirer.List('distro',
                          message="On which distro do you want to install the package?",
                          choices=['Ubuntu 22.04', 'Ubuntu 20.04', 'Fedora', 'Arch Linux', "Arch Linux (AUR)",
                                                                                           'OpenSUSE Leap', 'Alpine'],
                          ),
        ]
        distro = inquirer.prompt(questions)["distro"]
        container_name = create_uuid()
        print("Pulling and creating the image, this may take some time...")
        with contextlib.redirect_stdout(io.BytesIO()):
            os.system("distrobox create -i {} -n {}".format(distros[distro][0], container_name))
        print("Installing Base Packages, may also take a few minutes...")
        with contextlib.redirect_stdout(io.BytesIO()):
            os.system("distrobox enter {} -- echo 0".format(container_name))
        command = distros[distro][1].format(target)
        os.system("distrobox enter {} -- sudo {}".format(container_name, command))
    elif extension.lower() == "deb":
        pass
    elif extension.lower() == "rpm":
        pass


cli.add_command(install)

if __name__ == "__main__":
    if len(sys.argv) == 1:
        click.echo("ERROR: No Command given")
        sys.exit(1)
    cli()
