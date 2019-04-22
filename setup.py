import io
import os
import sys
from shutil import rmtree
import subprocess

from setuptools import find_packages, setup, Command
from setuptools.command.test import test

base_dir = os.path.abspath(os.path.dirname(__file__))

# Package meta-data.
NAME = "grpcWSGI"
DESCRIPTION = "gRPC-Web + WSGI"
URL = "https://github.com/public/grpcWSGI"
EMAIL = "alexs@prol.etari.at"
AUTHOR = "Alex Stapleton"
REQUIRES_PYTHON = ">=3.6.0"
VERSION = None

# What packages are required for this module to be executed?
REQUIRED = ["grpcio", "requests"]

# What packages are optional?
EXTRAS = {
    # 'fancy feature': ['django'],
}

# What packages are needed to run the tests?
TESTS_REQUIRED = ["grpcio-tools", "pytest", "pytest-mockservers", "requests"]

# The rest you shouldn't have to touch too much :)
# ------------------------------------------------
# Except, perhaps the License and Trove Classifiers!
# If you do change the License, remember to change the Trove Classifier for that!


# Import the README and use it as the long-description.
# Note: this will only work if 'README.md' is present in your MANIFEST.in file!
try:
    with io.open(os.path.join(base_dir, "README.md"), encoding="utf-8") as f:
        long_description = "\n" + f.read()
except FileNotFoundError:
    long_description = DESCRIPTION

# Load the package's __version__.py module as a dictionary.
about = {}
if not VERSION:
    with open(os.path.join(base_dir, NAME, "__version__.py")) as f:
        exec(f.read(), about)
else:
    about["__version__"] = VERSION


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


class PyTest(test):
    def run_tests(self):
        # Import here because in module scope the eggs are not loaded.
        import pytest

        test_args = [os.path.join(base_dir, "tests")]

        print("Building protos...")
        print(os.getcwd())
        code = subprocess.call(
            " python -m grpc.tools.protoc"
            " --proto_path=tests/protos/"
            " --python_out=."
            " --grpc_python_out=."
            " tests/protos/tests/helloworld.proto",
            shell=True,
        )

        if code:
            sys.exit(code)

        errno = pytest.main(test_args)
        sys.exit(errno)


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
        packages=find_packages(exclude=["tests", "*.tests", "*.tests.*", "tests.*"]),
        # If your package is a single module, use this instead of 'packages':
        # py_modules=['mypackage'],
        # entry_points={
        #     'console_scripts': ['mycli=mymodule:cli'],
        # },
        install_requires=REQUIRED,
        extras_require=EXTRAS,
        tests_require=TESTS_REQUIRED,
        include_package_data=True,
        license="MIT",
        classifiers=[
            # Trove classifiers
            # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
            "License :: OSI Approved :: MIT License",
            "Programming Language :: Python",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: Implementation :: CPython",
            "Programming Language :: Python :: Implementation :: PyPy",
        ],
        # $ setup.py publish support.
        cmdclass={"upload": UploadCommand, "test": PyTest},
    )
