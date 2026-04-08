from setuptools import setup, find_packages

setup(
    name="avgeosys",
    version="1.0.0",
    author="João Marcos Rezende Sasdelli Gonçalves",
    description="AVGeoSys - PPK & EXIF Geotagging Tool",
    packages=find_packages(include=["avgeosys", "avgeosys.*"]),
    include_package_data=True,
    install_requires=[
        "piexif",
        "simplekml",
        "pandas",
        "numpy",
        "matplotlib",
        "folium",
        "google-auth",
        "google-api-python-client",
    ],
    entry_points={
        "console_scripts": [
            "avgeosys=avgeosys.cli.cli:main",
        ],
    },
    python_requires=">=3.8",
)
