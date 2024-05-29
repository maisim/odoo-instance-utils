from setuptools import setup, find_packages

setup(
    name="odoo-instance-utils",
    version="0.1",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click",
        "click-odoo",
        "pyyaml",
    ],
    entry_points={
        "console_scripts": [
            "odoo-instance=commands.main:cli",
        ],
    },
)
