import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pyrodantic",
    version="0.0.5",
    author="Matthew Williams",
    author_email="mgwilliams@gmail.com",
    description="Pydantic models for Firestore",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mgwilliams/pyrodantic",
    packages=setuptools.find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=["pydantic", "google-cloud-firestore"],
)
