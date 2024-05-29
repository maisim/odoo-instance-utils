# odoo-instance

This is a work in progress, don't trust 


`odoo-instance` is a command-line tool to manage Odoo instances with ease. It provides various subcommands to generate configuration files, retrieve repository information, and more.

### Features

- Generate `repos.yml` for Git repositories in your Odoo instance.
- Retrieve and manage addon information.
- List and manage Python dependencies for Odoo addons.

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/maisim/odoo-instance-utils
   ```

2. Navigate to the project directory:
   ```bash
   cd odoo-instance-utils
   ```

3. Install the package:
   ```bash
   pip install -e .
   ```

### Usage

After installation, you can use the `odoo-instance` command. Below are some examples of how to use it.

#### Generate `repos.yml`

This command generates a `repos.yml` file containing information about the Git repositories in your Odoo instance.

```bash
odoo-instance -d <database_name> -c /etc/odoo/odoo.conf generate_repos_yml -o /tmp/repos.yml
```

**Options:**
- `-d` : Specify the Odoo database name.
- `-c` : Path to the Odoo configuration file.
- `generate_repos_yml` : Subcommand to generate the `repos.yml` file.
- `-o` : Output file path for the generated `repos.yml`.

### Example

To generate a `repos.yml` file for the database `myodoodbname` with the configuration file located at `/etc/odoo/odoo.conf` and output the results to `/tmp/repos.yml`, you would run:

```bash
odoo-instance -d myodoodbname -c /etc/odoo/odoo.conf generate_repos_yml -o /tmp/repos.yml
```

### Development

TODO


### TODO

- add other subcommands
- add tests

### License

This project is licensed under the AGPL 3 License. See the `LICENSE` file for details.

### Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

For any questions or suggestions, please open an issue or contact the maintainers.
