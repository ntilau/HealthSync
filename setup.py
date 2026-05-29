from setuptools import setup

setup(
    name="health-sync",
    version="0.1.0",
    description="Utilities for syncing Samsung Health data into Google Fit",
    py_modules=["push"],
    install_requires=[
        "google-auth>=2.35.0",
        "google-auth-oauthlib>=1.2.1",
        "google-api-python-client>=2.161.0",
    ],
    python_requires=">=3.10",
)
