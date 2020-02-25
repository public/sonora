import io
import os
import sys
from shutil import rmtree

from setuptools import find_packages, setup, Command

base_dir = os.path.abspath(os.path.dirname(__file__))

NAME = "sonora"
DESCRIPTION = "gRPC-Web for Python"
URL = "https://github.com/public/sonora"
EMAIL = "alexs@prol.etari.at"
AUTHOR = "Alex Stapleton"
REQUIRES_PYTHON = ">=3.7.0"

REQUIRED = ["grpcio", "requests", "aiohttp", "async-timeout"]

TESTS_REQUIRED = [
    "grpcio-tools",
    "pytest",
    "pytest-mockservers",
    "pytest-asyncio",
    "pytest-benchmark",
    "requests",
    "bjoern",
    "uvicorn",
    "aiohttp[speedups]",
]

EXTRAS = {"tests": TESTS_REQUIRED}

with io.open(os.path.join(base_dir, "README.md"), encoding="utf-8") as f:
    long_description = "\n" + f.read()

about = {}
with open(os.path.join(base_dir, NAME, "__version__.py")) as f:
    exec(f.read(), about)


class UploadCommand(Command):
    """Support setup.py upload."""

    description = "Build and publish the package."
    user_options = []

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print("\033[1m{0}\033[0m".format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        try:
            self.status("Removing previous builds…")
            rmtree(os.path.join(base_dir, "dist"))
        except OSError:
            pass

        self.status("Building Source and Wheel (universal) distribution…")
        os.system("{0} setup.py sdist bdist_wheel --universal".format(sys.executable))

        self.status("Uploading the package to PyPI via Twine…")
        os.system("twine upload dist/*")

        self.status("Pushing git tags…")
        os.system("git tag v{0}".format(about["__version__"]))
        os.system("git push --tags")

        sys.exit()


if __name__ == "__main__":
    # Where the magic happens:
    setup(
        name=NAME,
        version=about["__version__"],
        description=DESCRIPTION,
        long_description=long_description,
        long_description_content_type="text/markdown",
        author=AUTHOR,
        author_email=EMAIL,
        python_requires=REQUIRES_PYTHON,
        url=URL,
        packages=find_packages(exclude=["tests", "tests.*"]),
        install_requires=REQUIRED,
        extras_require=EXTRAS,
        tests_require=TESTS_REQUIRED,
        include_package_data=True,
        license="Apache License, Version 2.0",
        classifiers=[
            "License :: OSI Approved :: Apache Software License",
            "Programming Language :: Python",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: Implementation :: CPython",
        ],
        cmdclass={"upload": UploadCommand},
    )
