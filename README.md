# Overview

Welcome to the `alfred-python` SDK, the official Python library for interfacing with Alfred, your intelligent process automation platform. This SDK provides a simple and efficient way to integrate Alfred's capabilities into your Python applications.

## Alfred

Alfred is a powerful document processing platform that enables you to extract, index, and search through large document collections with ease. It offers a wide range of features, including:

- **Job Management**: Provides a robust job management system that allows you to schedule and monitor document processing jobs.

- **Tagging**: Tag documents based on their content, making it easy to organize and search through large document collections.

- **Extraction**: Can extract specific data from PDFs, images, and other documents with ease using its powerful extraction engine.

- **Indexing**: Powerful indexing engine that can index and search through millions of documents in seconds.

- **Integration**: Alfred can be easily integrated into your existing applications using its powerful API and SDKs.

- **Scalability**: Alfred is designed to scale with your needs, whether you're processing thousands of documents a day or millions.

### Features

- **Comprehensive Authentication Support**: Seamlessly handles OAuth, HMAC, and API key authentication methods, simplifying the process of connecting to the Alfred API.

- **Domain-Specific Operations**: Offers specialized support for File and Job operations, enabling developers to intuitively manage and interact with API resources.

- **Cross-Platform Compatibility**: Designed to be fully compatible across .NET Core, .NET Standard, and .NET Framework 4.7.2, ensuring broad usability in diverse development environments.

- **Minimal Dependencies**: Crafted to minimize external dependencies, facilitating an easier integration and deployment process with reduced conflict risk.

## Prerequisites

- Python v3.8+ installed on your development machine.
- An active Alfred API key for authentication.

## Installation

To integrate the Alfred python library into your python project, install the package via Pypy:

```bash
pip install alfred-python
```

# Getting Started

Check out this simple example to get up and running (this script creates a new session for uploading local files and its using the API key authentication):

```python
from alfred.rest import AlfredClient
from alfred.base.config import Configuration

config = Configuration.v1()
auth_config = {"api_key": "AXXXXXXXXXXXXXXXXXXXXXX"}

client = AlfredClient(config, auth_config)

result = client.sessions.create()
print(result)
```

## Initialize the Client (Step 1)

Begin by creating an instance of the Alfred client using your preferred authentication method.

### Authentication Methods

The following examples demonstrate how to initialize the Alfred client with different authentication methods:

- For API key authentication, use the following method with the API key:

   ```python
   auth_config = {"api_key": "AXXXXXXXXXXXXXXXXXXXXXX"}
   ```

- For OAuth authentication, specify the method and credentials explicitly.
- For HMAC authentication, provide the secret key and public key

## Sessions (Step 2)

Then create a session to be able to upload files and interact with jobs.

A Session is a mechanism designed for asynchronous file uploads. It serves as a container or grouping for files that are uploaded at different times or from various sources, but are all part of a single Job. To see more information visit our [official documentation](https://docs.tagshelf.dev/enpoints/deferred-session).

### Get existing session by ID

```python
# Get a session by ID
>>> result = client.sessions.get("XXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXX")
>>> print(result)

{'id': '3386f840-74e2-4bd8-92a7-57e829e46d05', 'creation_date': '2024-05-10T20:32:43.85', 'update_date': '2024-05-10T20:32:43.85', 'status': 'open', 'user_name': 'API Key 1', 'company_id': '286e2ed0-3626-4faa-a745-8ebf3488fbd7', 'job_id': None}
```  

### Create a new session

```python
# Create a session
>>> result = client.sessions.create()
>>> print(result)

{'session_id': '3386f840-74e2-4bd8-92a7-57e829e46d05'}
```

## Files (Step 3)

After creating and having an open session, upload the files you want to process in your jobs.

File is an individual document or data unit undergoing specialized operations tailored for document analysis and management. To see more information visit our [official documentation](https://docs.tagshelf.dev/enpoints/file).

You can upload a file by 2 different methods:
- Uploading a remote file from your local machine.
- Upload a remote file from a remote location with its URL.

### Get file by ID

```python
# Get a file by ID
>>> result = client.files.get("XXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXX")
>>> print(result)

{'id': '9f8447ef-4090-4a29-ac7c-7ae2f23ca110', 'creation_date': '2024-05-13T16:22:22.593', 'update_date': '2024-05-13T16:22:22.593', 'file_name': 'CertificacionMeta.pdf', 'file_name_without_extension': 'CertificacionMeta', 'blob_name': '9f8447ef-4090-4a29-ac7c-7ae2f23ca110', 'blob_url': 'https://testbox.blob.core.windows.net/tsc-286e2ed0-3626-4faa-a745-8ebf3488fbd7-files/9f8447ef-4090-4a29-ac7c-7ae2f23ca110', 'user_name': None, 'md5_hash': 'GiZkvwxF0QwxbALzdPX6gA==', 'content_type': 'application/octet-stream', 'channel': 'api', 'should_be_classified': True, 'classifier': None, 'classification_score': 0.0, 'status': 'uploaded', 'input_type': 'single_unit', 'is_duplicate': False, 'is_duplicate_by_values': False, 'duplicate_origin_id': None, 'tag_id': None, 'is_parent': False, 'parent_id': None, 'deferred_session_id': None, 'tag_name': None, 'company_id': '286e2ed0-3626-4faa-a745-8ebf3488fbd7', 'file_size': 285901, 'proposed_tag_id': None, 'proposed_tag_variance': 0.0, 'classification_score_above_deviation': True, 'confirmed_tag_id': None, 'confirmed_by': None, 'manual_classification': False, 'metadata': '', 'page_count': 1, 'page_number': -1}
```

### Download file by ID

```python
# Download a file by ID
>>> result = client.files.download("XXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXX")
>>> with open(result.get("original_name"), "wb") as f:
>>>   f.write(result.get("file").getvalue())
```

### Upload remote file

```python
# Upload a remote file
>>> result = client.files.upload({
>>>    "url": "<File URL>",
>>>    "metadata": {}
>>> })
>>> print(result)
```

### Upload a local file

```python
>>> with open("<Path to local file>", "rb") as upload_file:
>>>    result = client.files.upload_file({
>>>       "file": upload_file,
>>>       "session_id": "XXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXX",
>>>       "metadata": {}
>>>    })
>>>    print(result)

{'file_id': '9f8447ef-4090-4a29-ac7c-7ae2f23ca110'}
```

## Jobs (Step 4)

A Job represents a single unit of work that groups one or more Files within Alfred. To see more information visit our [official documentation](https://docs.tagshelf.dev/enpoints/job).

### Get job by ID

```python
# Get a job by ID
>>> result = client.jobs.get("XXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXX")
>>> print(result)

{'id': 'fc7f1ca9-2486-4ccb-8229-b658c3c73050', 'creation_date': '2024-05-13T17:41:20.133', 'has_job_request_info': False, 'job_request_date': None, 'update_date': '2024-05-13T17:41:25.087', 'company_id': '286e2ed0-3626-4faa-a745-8ebf3488fbd7', 'bulk_id': None, 'deferred_session_id': '5557f5c2-164b-4126-a55f-3603f2c5ee8b', 'user_name': 'API Key 1', 'channel': 'api', 'source': None, 'container': None, 'remote_file_name': None, 'remote_file_names': None, 'merge': False, 'decompose': False, 'propagate_metadata': False, 'parent_file_prefix': None, 'decomposed_page_rotation': -1, 'metadata': None, 'file_count': 1, 'file_sources_count': 1, 'metadata_objects_count': 0, 'finished_files': 1, 'files': [{'id': 'da09e1c9-35e6-4b29-83d9-2c2af27ee9e1', 'creation_date': '2024-05-13T17:41:19.727', 'update_date': '2024-05-13T17:41:27.383', 'file_name': 'CertificacionMeta-6.pdf', 'tag_name': '', 'is_parent': False, 'is_children': False, 'status': 'finished'}], 'retries': 0, 'exceeded_retries': False, 'file_urls': ['https://testbox.blob.core.windows.net/tsc-286e2ed0-3626-4faa-a745-8ebf3488fbd7-files/da09e1c9-35e6-4b29-83d9-2c2af27ee9e1'], 'error_messages': [], 'stage': 'completed', 'priority': 'normal', 'input_source_type': 'deferred_upload', 'start_date': '2024-05-13T17:41:20.21', 'email_from': None, 'email_subject': None, 'email_body': None}
```

### Create new job

```python
# Create a job
>>> job = {"session_id": "3386f840-74e2-4bd8-92a7-57e829e46d05"}
>>> result = client.jobs.create(job)
>>> print(result)

{'job_id': '4c7d6041-2293-42c6-991d-4c9e9af6f9d0'}
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
```

## Data Points (Step 5)

Data Points are the core of Alfred's platform and represent data that you want to extract. To see more information visit our [official documentation](https://docs.tagshelf.dev/enpoints/metadata).

> [!IMPORTANT]
> Data Points where previously known as Metadata.

### Get Data Point by File ID

```python
# Get a data point by file ID
>>> result = client.data_points.get_values("XXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXX")
>>> print(result)
```

# Real-time Events
The `alfred-python` library provides a way to listen to events emitted by Alfred IPA in real-time through a websockets implementation. This feature is particularly useful when you need to monitor the progress of a Job, File, or any other event that occurs within the Alfred platform. To see more information visit our [official documentation](https://docs.tagshelf.dev).

## Initalizing Instance

To get started, you need to create an instance of the `AlfredRealTimeClient` class.

```python
from src.alfred.realtime import AlfredRealTimeClient
from src.alfred.base.config import Configuration
from src.alfred.http.typed import AuthConfiguration

config = Configuration.v1()

auth_config = AuthConfiguration({
    "api_key": "AXXXXXXXXXXXXXXXXXXXXXX"
})

client = AlfredRealTimeClient(config, auth_config, verbose=True)
```

## File Events
These events are specifically designed to respond to a variety of actions or status changes related to Files. To see more details about File events, visit our [official documentation](https://docs.tagshelf.dev/event-api/fileevents).

```python 
client.on_file_event(lambda data: print(data))
```

### File Event List

| Event Type                   | Description                                             |   |   |   |
|------------------------------|---------------------------------------------------------|---|---|---|
| FileAddToJobEvent            | Triggered when a file is added to a job for processing. |   |   |   |
| FileCategoryCreateEvent      | Occurs when a new category is created for a file.       |   |   |   |
| FileCategoryDeleteEvent      | Signals the deletion of a file's category.              |   |   |   |
| FileChangeTagEvent           | Indicates a change in the tag associated with a file.   |   |   |   |
| FileDoneEvent                | Marks the completion of file processing.                |   |   |   |
| FileExtractedDataCreateEvent | Triggered when new data is extracted from a file.       |   |   |   |
| FileExtractedDataDeleteEvent | Occurs when extracted data from a file is deleted.      |   |   |   |
| FileFailedEvent              | Indicates a failure in file processing.                 |   |   |   |
| FileMoveEvent                | Signals the movement of a file within the system.       |   |   |   |
| FileMoveToPendingEvent       | Triggered when a file is moved to a pending state.      |   |   |   |
| FileMoveToRecycleBinEvent    | Indicates movement of a file to the recycle bin.        |   |   |   |
| FilePropertyCreateEvent      | Reflects the creation of a file property.               |   |   |   |
| FilePropertyDeleteEvent      | Signals the deletion of a file property.                |   |   |   |
| FileRemoveTagEvent           | Signals the removal of a tag from a file.               |   |   |   |
| FileStatusUpdateEvent        | Indicates an update in the file's status.               |   |   |   |
| FileUpdateEvent              | Triggered when a file is updated in any manner.         |   |   |   |

## Job Events
Alfred performs asynchronous document classification, extraction, and indexing on a variety of file types. The events detailed here offer insights into how a Job progresses, fails, retries, or completes its tasks. To see more details about Job events, visit our [official documentation](https://docs.tagshelf.dev/event-api/jobevents).

```python
client.on_job_event(lambda data: print(data))
```

### Job Event List

| Event Name               | Job Events                                                            |   |   |   |
|--------------------------|-----------------------------------------------------------------------|---|---|---|
|  JobCreateEvent          | Triggered when a new job is instantiated for file operations.         |   |   |   |
|  JobExceededRetriesEvent | Fires when job exceeds maximum retry attempts for a stage.            |   |   |   |
|  JobFailedEvent          | Occurs when a job halts due to an unrecoverable error.                |   |   |   |
|  JobFinishedEvent        | Triggered when job successfully completes all workflow stages.        |   |   |   |
|  JobInvalidEvent         | Fires when job fails initial validation of input files or parameters. |   |   |   |
|  JobRetryEvent           | Triggered when job retries a stage after a recoverable failure.       |   |   |   |
|  JobStageUpdateEvent     | Occurs when job transitions from one workflow stage to another.       |   |   |   |
|  JobStartEvent           | Triggered when job begins its workflow and state machine.             |   |   |   |

## Custom Events
This enables you to select the specific event you wish to monitor. It's particularly beneficial when new events are introduced that have not yet received official support within the library.

```python
client.on("custom-event", lambda data: print(data))
```

# Configuration

This section provides detailed instructions and guidelines for configuring the SDK to interface effectively with the target API.

## Retry Policy

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

# Contributing

Contributions to improve this library are welcome. Please feel free to fork the repository, make your changes, and submit a pull request for review.

# License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/tagshelfsrl/dotnet-alfred-api-wrapper/blob/feature/AL-887/LICENSE) file for details.

# Acknowledgements

Thanks to all the contributors who invest their time into making this library better.