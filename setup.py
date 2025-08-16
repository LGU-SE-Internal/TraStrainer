"""Setup configuration for TraStrainer package."""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip() for line in fh if line.strip() and not line.startswith("#")
    ]

# Add new dependencies for Polars support and CLI
additional_requirements = [
    "polars>=0.20.0",
    "typer>=0.9.0",
    "rich>=13.0.0",  # For better CLI output
]

requirements.extend(additional_requirements)

setup(
    name="trastrainer",
    version="1.0.0",
    author="TraStrainer Team",
    author_email="team@trastrainer.com",
    description="An adaptive sampler for distributed traces with system runtime state",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/trastrainer/trastrainer",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Monitoring",
        "Topic :: System :: Distributed Computing",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "isort>=5.0",
            "flake8>=3.8",
            "mypy>=0.800",
        ],
    },
    entry_points={
        "console_scripts": [
            "trastrainer=trastrainer.main:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
