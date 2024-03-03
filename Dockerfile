FROM python:3.9

WORKDIR /usr/src/app

COPY Pipfile .
COPY Pipfile.lock .

RUN pip install pipenv \
    && pipenv install --system --deploy --ignore-pipfile

# Create and switch to a new user
RUN useradd --create-home appuser
WORKDIR /home/appuser
USER appuser
RUN mkdir /home/appuser/data

# Install application into container
COPY ./app ./app
