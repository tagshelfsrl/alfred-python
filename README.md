# Overview

Welcome to the `alfred-python` SDK, the official Python library for interfacing with Alfred, your intelligent process automation platform. This SDK provides a simple and efficient way to integrate Alfred's capabilities into your Python applications.

## Prerequisites

- Python v3.8+

## Usage

Check out this simple example to get up and running:

```python
from alfred.rest import AlfredClient
from alfred.base.config import Configuration

config = Configuration.v1()
auth_config = {"api_key": "AXXXXXXXXXXXXXXXXXXXXXX"}

client = AlfredClient(config, auth_config)

values = client.data_points.get_values("XXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXX")
print(values)
```

### Sessions

A Session is a mechanism designed for asynchronous file uploads. It serves as a container or grouping for files that are uploaded at different times or from various sources, but are all part of a single Job. To see more information visit our [official documentation](https://docs.tagshelf.dev/enpoints/deferred-session).

#### Get session by ID

```python
# Get a session by ID
result = client.sessions.get("XXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXX")
print(result)
```

#### Create session

```python
# Create a session
result = client.sessions.create()
print(result)
```

### Jobs

A Job represents a single unit of work that group one or more Files within Alfred. To see more information visit our [official documentation](https://docs.tagshelf.dev/enpoints/job).

#### Get job by ID

```python
# Get a job by ID
result = client.jobs.get("XXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXX")
print(result)
```

#### Create job

```python
job = {
   "session_id": "session-id",
   "propagate_metadata": True,
   "merge": True,
   "decompose": True,
   "metadata": {
      "key": "value",
   },
   "channel": "channel",
   "parent_file_prefix": "prefix",
   "page_rotation": 90,
   "container": "container",
   "file_name": "file-name",
   "file_names": ["file-name-1", "file-name-2"],
}

# Create a job
result = client.jobs.create(job)
print(result)
```

Here is a description for each valid argument when creating a job:

| Parameter          | Type     | Description                                                                                                                              |
| ------------------ | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| session_id         | string   | Session ID                                                                                                                               |
| metadata           | any      | Metadata of the job                                                                                                                      |
| propagate_metadata | boolean  | If `true` ensures that the provided metadata at the Job level is attached to all the specified Files.                                    |
| merge              | boolean  | If `true`, when all provided Files are either images or PDFs, the system combines them into a single file for the purpose of processing. |
| decompose          | boolean  | If `true`, when the provided File is a PDF, the system will decompose it into individual pages for processing.                           |
| channel            | string   | Channel                                                                                                                                  |
| parent_file_prefix | string   | The `parent_file_prefix` parameter is used to specify a virtual folder destination for the uploaded files.                               |
| page_rotation      | number   | Page rotation                                                                                                                            |
| container          | string   | Virtual container where the referenced remote file is located.                                                                           |
| file_name          | string   | Unique name of the file within an object storage source.                                                                                 |
| file_names         | string[] | Array of unique names of the files within an object storage source.                                                                      |

### Files

File is an individual document or data unit undergoing specialized operations tailored for document analysis and management. To see more information visit our [official documentation](https://docs.tagshelf.dev/enpoints/file).

#### Get file by ID

```python
# Get a file by ID
result = client.files.get("XXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXX")
print(result)
```

#### Download file by ID

```python
# Download a file by ID
result = client.files.download("XXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXX")

with open(result.get("original_name"), "wb") as f:
   f.write(result.get("file").getvalue())
```

#### Upload remote file

```python
# Upload a remote file
result = client.files.upload({
   "url": "<File URL>",
   "metadata": {}
})
print(result)
```

#### Upload a local file

```python
with open("<Path to local file>", "rb") as upload_file:
   result = client.files.upload_file({
      "file": upload_file,
      "session_id": "XXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXX",
      "metadata": {}
   })
   print(result)
```

### Data Points

Data Points are the core of Alfred's platform and represent data that you want to extract. To see more information visit our [official documentation](https://docs.tagshelf.dev/enpoints/metadata).

> [!IMPORTANT]
> Data Points where previously known as Metadata.

#### Get Data Point by File ID

```python
# Get a data point by file ID
result = client.data_points.get_values("XXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXX")
print(result)
```

## Configuration

This section provides detailed instructions and guidelines for configuring the SDK to interface effectively with the target API.

### Retry Policy

In this SDK, we implement automatic retries to enhance the reliability of network requests. However, to maintain the integrity of data transactions, retries are only enabled for HTTP methods that are considered idempotent. Idempotent methods are those that can be called multiple times without different outcomes. Thus, retries are applied only to the following HTTP methods:

- `GET`: Retrieves data from the server without changing any state.
- `PUT`: Updates a resource in a way that it can be repeatedly updated without changing the outcome beyond the initial application.
- `DELETE`: Removes a resource and subsequent deletions of the same resource are redundant.
- `HEAD`: Fetches metadata about a resource without side-effects.
- `OPTIONS`: Retrieves supported communication options for a given URL or server without causing any side effects.

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
