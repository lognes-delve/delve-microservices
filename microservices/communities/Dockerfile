FROM python:3-slim

# Add an optional argument for the github PAT to get access to
# the common-lib repo.
ARG GH_TOKEN

# This is where the app is hosted in the container
EXPOSE 8080

WORKDIR /code

# Make sure that all the pretty packages are nice and updated
RUN apt-get update -y
RUN apt-get upgrade -y

# We need git to install remote dependencies from github
RUN apt-get install git -y

# Generate ssh credentials for git stuff
RUN mkdir ~/.ssh && ln -s /run/secrets/host_ssh_key ~/.ssh/id_rsa

# Copy dependencies
COPY requirements.txt .

# Replace the placeholder string with the PAT from env
RUN sed -i "s|\${GH_TOKEN}|'${GH_TOKEN}'|g" requirements.txt

# Install the requirements
RUN pip install -r requirements.txt

# Copy all of the code from ./src into the working directory
COPY ./src /code/src

# - run gunicorn, referencing the /src/app file, and the "app" object within it
# - spawn 4 workers
# - use the UvicornWorker so async stuff doesn't break
# - expose publicly (0.0.0.0) and bind to port 8080 
CMD ["gunicorn", "src.app:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080"]

