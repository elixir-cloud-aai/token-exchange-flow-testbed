# Installation

Clone the repository, then build the image. All commands run from the repository's folder, in any shell.

```sh
git clone https://github.com/elixir-cloud-aai/token-exchange-flow-testbed.git
cd token-exchange-flow-testbed
docker compose build
```

The image holds no secrets and needs no build arguments. Go on with [Checking the setup](checking.md).

To work on the testbed itself, with [uv](https://docs.astral.sh/uv/) and Python on your machine, see [Development](../about/development.md).
