# MP3Scan utility in Python

This repo contains an MP3Scan utility in Python code.

This utility extracts information from an MP3 file, including:

* MPEG audio
* ID3 v1 tag
* ID3 v2 tag
* Embedded Lyrics
* Embedded Album Art

## Requirements

* You must have the following installed:
  * Python 3

* The code was written for:
  * Python 3

## Use a Virtual Environment

A Python environment is a self-contained directory that includes a specific version of Python and a set of installed packages. It is recommended using Python virtual environments for each project.

1. Create a virtual environment

  Open your terminal and run:

  ```bash
  python -m venv .venv
  ```

  This creates a folder named `.venv` containing the environment.

2. Activate the environment

 On Windows:

 ```bash
.venv\Scripts\activate
 ```

 On macOS/Linux:

 ```bash
 source .venv/bin/activate
 ```

 Once activated, your terminal will show the environment name, like this:

 ```bash
 (.venv) $
 ```

3. Install packages inside the environment

 Now you can install packages without affecting your global Python setup:

 ```bash
 pip install mutagen
 ```

4. Deactivate the environment

 When you're done, simply run:

 ```bash
 deactivate
 ```

## Install library packages

Install the specified python packages.

  ```bash
  pip install -r requirements.txt
  ```

On the other hand, you can install individual library packages on a per-project basis depending on your needs.

The list of individual library packages that the application uses:

* Audio Tags
  
  * `mutagen`

    Read and write audio tags for many formats.

    ```bash
    pip install mutagen
    ```

* Imaging Library
  
  * `pillow`

    Python Imaging Library (fork).

    ```bash
    pip install pillow
    ```

## Using the utility

* This utility reads information from MP3 files.
  
* Run the utility from the command line:

  ```bash
  python mp3scan.py <file_name>
  ```
  
* You will get the following information:

  * MPEG audio
  * ID3 v1 tag
  * ID3 v2 tag
  * Embedded Lyrics
  * Embedded Album Art

## Testing

This project includes unit tests to verify the functionality of the code.

To run the tests, execute the following command in your terminal:

```bash
python test_mp3scan.py
```
Or if you want more details about the exit:

```bash
python test_mp3scan.py -v
```

Or using the unittest module directly:

```bash
python -m unittest test_mp3scan.py
```

## License

This code is released under the MIT License. See LICENSE file.