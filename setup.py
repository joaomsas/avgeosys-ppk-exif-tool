from setuptools import setup, find_packages

setup(
    name="avgeosys",
    version="0.3.02",
    author="João Marcos Rezende Sasdelli Gonçalves",
    description="AVGeoSys - PPK & EXIF Tool",
    packages=find_packages(include=["avgeosys", "avgeosys.*"]),
    include_package_data=True,
    install_requires=[
        "piexif",
        "simplekml",
        "pandas",
        "numpy",
    ],
    entry_points={
        "console_scripts": [
            "avgeosys=avgeosys.cli.cli:main",
        ],
    },
    python_requires=">=3.8",
)