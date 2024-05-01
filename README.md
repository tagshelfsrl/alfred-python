## Overview

Welcome to the `alfred-python` SDK, the official Python library for interfacing with Alfred, your intelligent process automation platform. This SDK provides a simple and efficient way to integrate Alfred's capabilities into your Python applications.

## Prerequisites

- Python v3.8+

## Usage

Work in progress...

## Configuration

This section provides detailed instructions and guidelines for configuring the SDK to interface effectively with the target API.

### Retry Policy

In this SDK, we implement automatic retries to enhance the reliability of network requests. However, to maintain the integrity of data transactions, retries are only enabled for HTTP methods that are considered idempotent. Idempotent methods are those that can be called multiple times without different outcomes. Thus, retries are applied only to the following HTTP methods:

- GET: Retrieves data from the server without changing any state.
- PUT: Updates a resource in a way that it can be repeatedly updated without changing the outcome beyond the initial application.
- DELETE: Removes a resource and subsequent deletions of the same resource are redundant.
- HEAD: Fetches metadata about a resource without side-effects.
- OPTIONS: Retrieves supported communication options for a given URL or server without causing any side effects.

For non-idempotent methods like POST and PATCH, the SDK does not perform retries by default because doing so could potentially result in unwanted side effects or duplicate operations. If you need to enable retries for these methods under specific circumstances, please handle them cautiously in your application logic.

## Development Setup

### Setting up the development environment

To contribute to `alfred-python`, you'll need to set up a Python development environment. We recommend using Conda, a popular package and environment management system. Here’s how to set it up:

1. **Install Conda**: If you do not have Conda installed, you can download and install it from [Miniconda](https://docs.conda.io/en/latest/miniconda.html) (a minimal installer) or [Anaconda](https://www.anaconda.com/products/distribution) (a full-featured distribution).

2. **Create a new Conda environment**: Open your terminal and run the following command to create a new environment named `alfred-python`:

   ```bash
   conda create --name alfred-python python=3.8 -y
   ```

3. **Activate the environment**: Activate the newly created environment by running:

   ```bash
   conda activate alfred-python
   ```

4. **Install dependencies**: With the environment activated, install the required dependencies by running:

   ```bash
   pip install -r requirements.txt
   ```

This sets up a basic Python environment tailored for development purposes.

### Optional: Setting up a testing environment

For testing and development, it's often useful to install the package in a way that reflects changes in real-time. To do this, you can install the package in editable mode. Here’s how to create a separate environment for testing and install the SDK:

1. **Create a testing environment**: It's a good practice to separate testing and development environments to avoid conflicts. Create a new environment named `alfred-python-test`:

   ```bash
   conda create --name alfred-python-test python=3.8 -y
   ```

2. **Activate the testing environment**:

   ```bash
   conda activate alfred-python-test
   ```

3. **Install the SDK in editable mode**: Navigate to the root directory of the `alfred-python` project and run:

   ```bash
   pip install --editable .
   ```

## Building the Project

To package `alfred-python` into distributable formats such as source archives and wheels, you will need to use the `build` module, a modern tool for building packages that adheres to PEP 517. Follow these steps to build the project:

### Preparing the build environment

Before building the project, ensure that your development environment is activated and up-to-date. If you don’t have an environment set up, please refer to the [Development Setup](#development-setup) section to create and activate one.

### Installing the build Tool

With your environment ready, install the `build` package. This package provides a simple, reliable way to build your project. Install it using pip:

```bash
pip install -U build
```

### Running the build process

Once `build` is installed, you can generate the build artifacts by running the following command from the root directory of your project:

```bash
python -m build
```

This command will produce a source distribution (`tar.gz`) and a wheel file (`whl`) in the `dist/` directory. These files are what you would upload to a package index like PyPI, or distribute to other developers.
