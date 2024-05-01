## Overview

Welcome to the `alfred-python` SDK, the official Python library for interfacing with Alfred, your intelligent process automation platform. This SDK provides a simple and efficient way to integrate Alfred's capabilities into your Python applications.

## Prerequisites

- Python v3.8+

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

This command installs the SDK in a way that any changes you make to the source code will immediately affect the installed package, facilitating rapid testing and development.
