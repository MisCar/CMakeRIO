from os import walk, listdir
from os.path import (
    join,
    expanduser,
    isdir,
    join,
    relpath,
    exists,
    abspath,
    realpath,
    dirname,
)
from sys import argv
from dataclasses import dataclass
from io import BytesIO
from typing import Union, List
from urllib.error import HTTPError
from urllib.request import urlopen
from json import load
from zipfile import ZipFile

NI_LIBRARIES = ["visa", "runtime", "netcomm", "chipobject"]
WPILIB_LIBRARIES = [
    "wpilibc",
    "wpiutil",
    "wpimath",
    "ntcore",
    "cscore",
    "hal",
    "cameraserver",
]

NI_VERSION = "2022.2.3"
WPILIB_VERSION = "2022.1.1-beta-2"

INSTALL_ROOT = join(expanduser("~"), ".wpilib-headers")

SCRIPT_DIRECTORY = dirname(realpath(__file__))
VENDORDEPS = [
    load(open(join(SCRIPT_DIRECTORY, "vendordeps", f), "r"))
    for f in listdir(join(SCRIPT_DIRECTORY, "vendordeps"))
]


@dataclass
class Dependency:
    url: str
    category: str
    name: str
    version: str
    shared: bool

    def get(self, part: str) -> Union[ZipFile, None]:
        try:
            response = urlopen(
                f"{self.url}/{self.name}/{self.version}/{self.name}-{self.version}-{part}.zip"
            )
            return ZipFile(BytesIO(response.read()))
        except HTTPError:
            return None

    def headers(self) -> bool:
        headers_zip = self.get("headers")
        if headers_zip is None:
            return False

        headers_zip.extractall(
            join(
                INSTALL_ROOT,
                "headers",
                self.category,
                self.name.replace("-cpp", "").lower(),
            )
        )
        return True

    def install(self):
        print(f"Installing {self.category}.{self.name}")
        self.headers()


def generate_header_with_all_includes(path: str):
    if not isdir(path):
        return

    includes = []
    for root, directories, files in walk(join(INSTALL_ROOT, "headers")):
        if "Eigen" in root or "ntcore" in root or "cscore" in root:
            continue

        root = relpath(root, join(INSTALL_ROOT, "headers"))
        if "/" in root:
            root = root[root.index("/") + 1 :]
            if "/" in root:
                root = root[root.index("/") + 1 :]

        includes += map(
            lambda f: join(root, f.replace("\\", "/")),
            filter(
                lambda f: f.endswith(".h")
                and not (f == "MovingAverage.h" and root == "ctre/phoenix/signals")
                and not (f == "uv.h" and root == "wpiutil")
                and not root.startswith("uv")
                and f != "WPILibVersion.h"
                and not "jni" in f.lower(),
                files,
            ),
        )

    open(join(path, "IncludeAll.h"), "w").write(
        "/* THIS IS AN AUTOMATICALLY GENERATED FILE. YOU SHOULDN'T EDIT IT. */\n"
        + "\n".join(map(lambda include: f"#include <{include}>", includes))
    )


def until(s: str, part: str, remove: bool = False) -> str:
    if part not in s:
        return s
    return s[: s.index(part) + (0 if remove else len(part))]


def install() -> None:
    dependencies: List[Dependency] = []

    for library in NI_LIBRARIES:
        dependencies.append(
            Dependency(
                url="https://frcmaven.wpi.edu/ui/api/v1/download?repoKey=release&path=edu/wpi/first/ni-libraries",
                category="ni",
                name=library,
                version=NI_VERSION,
                shared=True,
            )
        )

    for library in WPILIB_LIBRARIES:
        dependencies.append(
            Dependency(
                url=f"https://frcmaven.wpi.edu/ui/api/v1/download?repoKey=release&path=edu/wpi/first/{library}",
                category="wpilib",
                name=f"{library}-cpp",
                version=WPILIB_VERSION,
                shared=False,
            )
        )

    for vendordep in VENDORDEPS:
        try:
            for d in vendordep["cppDependencies"]:
                dependencies.append(
                    Dependency(
                        url=(
                            f"{vendordep['mavenUrls'][0].removesuffix('/')}/{d['groupId'].replace('.', '/')}"
                            if d["version"] != "wpilib"
                            else "https://frcmaven.wpi.edu/ui/api/v1/download?repoKey=release&path=edu/wpi/first/wpilibNewCommands"
                        ),
                        category=until(vendordep["name"].lower(), "-", remove=True),
                        name=d["artifactId"],
                        version=(
                            d["version"] if d["version"] != "wpilib" else WPILIB_VERSION
                        ),
                        shared=d["sharedLibrary"],
                    )
                )
        except:
            pass

    i = 0
    for dependency in dependencies:
        print(f"Progress: {int(i / len(dependencies) * 100)}%")
        dependency.install()
        i += 1


def create_compile_flags(directory: Union[str, None] = None):
    if directory is None:
        directory = abspath(".")

    contents = ""

    for category in listdir(join(INSTALL_ROOT, "headers")):
        for library in listdir(join(INSTALL_ROOT, "headers", category)):
            contents += (
                "-I"
                + join(INSTALL_ROOT, "headers", category, library).replace("\\", "/")
                + "\n"
            )

    try:
        with open(join(directory, "build.gradle"), "r") as buildfile:
            build = buildfile.read()
            build = build[build.index("exportedHeaders") :]
            build = build[: build.index("}")]
            for row in build.split("\n")[1:-1]:
                row = row[row.index('"') + 1 :]
                row = row[: row.index('"')]
                contents += "-I" + join(directory, row).replace("\\", "/") + "\n"
    except:
        pass

    contents += "-std=c++17\n"
    contents += "-xc++\n"

    with open(join(directory, "compile_flags.txt"), "w") as compile_flags:
        compile_flags.write(contents)

    for category in listdir(join(INSTALL_ROOT, "headers")):
        for library in listdir(join(INSTALL_ROOT, "headers", category)):
            with open(
                join(INSTALL_ROOT, "headers", category, library, "compile_flags.txt"),
                "w",
            ) as compile_flags:
                compile_flags.write(contents)


if not exists(INSTALL_ROOT):
    install()

if len(argv) > 2:
    print("Generating compile_flags.txt")
    create_compile_flags(argv[2])
    print("Generating header with all includes")
    generate_header_with_all_includes(argv[1])
    print("Done")
else:
    print("Generating compile_flags.txt")
    create_compile_flags()
    print("Generating header with all includes")
    generate_header_with_all_includes(".")
    print("Done")
