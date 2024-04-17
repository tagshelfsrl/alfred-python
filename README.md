## [Python Application Name]

[Application description]

## Prerequisites

- Python v3.8+

## Running the application

1. Create a new python environment. We normally use Anaconda, but you can use any python environment manager you want.

   ```bash
   conda create -n <python environment name> python=3.8
   ```

2. Install dependencies using `pip`. This project depends on private hosted packages, so you have to setup a `.pypirc`.

   ```bash
   pip install -r requirements.txt
   ```

3. Create a dotenv file based on the `dot.env` file (do NOT update the `dot.env`, copy it and rename it `.env`).

4. Run the worker

   ```bash
   python run.py
   ```
