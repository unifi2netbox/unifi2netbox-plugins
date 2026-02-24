from setuptools import find_packages, setup

setup(
    name="netbox-unifi2netbox",
    version="0.1.0",
    description="NetBox plugin to sync UniFi inventory into NetBox",
    python_requires=">=3.10",
    packages=find_packages(exclude=("tests", "docs", "lxc", "tools")),
    py_modules=["main"],
    include_package_data=True,
    install_requires=[
        "pyotp~=2.9.0",
        "requests~=2.32.3",
        "pynetbox~=7.4.1",
        "PyYAML~=6.0.2",
        "python-dotenv~=1.0.1",
        "python-slugify~=8.0.4",
        "urllib3~=2.6.3",
    ],
    zip_safe=False,
)
