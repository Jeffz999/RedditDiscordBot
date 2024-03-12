# Use the micromamba Docker image
FROM mambaorg/micromamba:1.5.1

# Set the working directory in the container
WORKDIR /app

# Copy the environment.yml and your application to the working directory
COPY environment.yml /tmp/environment.yml
COPY . /app

# Install the environment and perform cleanup
RUN micromamba install -y -n base -f /tmp/environment.yml && \
    micromamba clean --all --yes

# Ensure Conda environment is activated for RUN commands
ARG MAMBA_DOCKERFILE_ACTIVATE=1 

# Set the PATH to include the micromamba binary
ENV PATH="/root/micromamba/bin:${PATH}"

# Command to run tests
CMD bash
