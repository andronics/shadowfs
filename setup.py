"""Setup configuration for ShadowFS."""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="shadowfs",
    version="1.0.0",
    author="Stephen Cox",
    author_email="",
    description="Dynamic Filesystem Transformation Layer",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/andronics/shadowfs",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: System :: Filesystems",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
    ],
    python_requires=">=3.11",
    install_requires=[
        "fusepy>=3.0.1",
        "pyyaml>=6.0",
        "jinja2>=3.1.2",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black==23.7.0",
            "flake8>=6.1.0",
            "mypy>=1.5.0",
            "pre-commit>=3.3.0",
        ],
        "transforms": [
            "markdown>=3.4.0",
        ],
        "metrics": [
            "prometheus-client>=0.16.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "shadowfs=shadowfs.application.shadowfs_main:main",
            "shadowfs-ctl=shadowfs.application.cli:main",
        ],
    },
)