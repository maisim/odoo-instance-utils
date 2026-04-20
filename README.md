# odoo-instance

This is a work in progress 


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
#### odoo-instance

##### Usage

```
Usage: odoo-instance [OPTIONS] COMMAND [ARGS]...

```
##### CLI Help

```
Usage: odoo-instance [OPTIONS] COMMAND [ARGS]...

Options:
  -c, --config FILE               Specify the Odoo configuration file. Other
                                  ways to provide it are with the ODOO_RC or
                                  OPENERP_SERVER environment variables, or
                                  ~/.odoorc (Odoo >= 10) or
                                  ~/.openerp_serverrc.
  -d, --database TEXT             Specify the database name. If present, this
                                  parameter takes precedence over the database
                                  provided in the Odoo configuration file.
  --log-level TEXT                Specify the logging level. Accepted values
                                  depend on the Odoo version, and include
                                  debug, info, warn, error.  [default: warn]
  --logfile FILE                  Specify the log file.
  --rollback                      Rollback the transaction even if the script
                                  does not raise an exception. Note that if
                                  the script itself commits, this option has
                                  no effect. This is why it is not named dry
                                  run. This option is implied when an
                                  interactive console is started.
  --installed-addons-only / --include-all-addons
                                  Work with installed addons only (default) or
                                  include not installed addons
  --help                          Show this message and exit.

Commands:
  generate-repos-yaml  Generate repos.yml file for git-aggregator.
  list-addons         List addons and their status
```



#### odoo-instance generate-repos-yaml

Generate repos.yml file for git-aggregator. If your addons come from git repositories, this command will generate a repos.yml file for git-aggregate.

##### Usage

```
Usage: odoo-instance generate-repos-yaml [OPTIONS]

```
##### CLI Help

```
Usage: odoo-instance generate-repos-yaml [OPTIONS]

  Generate repos.yml file for git-aggregator. If your addons come from git
  repositories, this command will generate a repos.yml file for git-aggregate.

Options:
  -o, --output PATH  Output file for repos.yml
  --help             Show this message and exit.
```



#### odoo-instance list-addons

List addons and their status

##### Usage

```
Usage: odoo-instance list-addons [OPTIONS]

```
##### Usage

```
Usage: odoo-instance [OPTIONS] COMMAND [ARGS]...

```
##### CLI Help

```
Usage: odoo-instance [OPTIONS] COMMAND [ARGS]...

Options:
  -c, --config FILE               Specify the Odoo configuration file. Other
                                  ways to provide it are with the ODOO_RC or
                                  OPENERP_SERVER environment variables, or
                                  ~/.odoorc (Odoo >= 10) or
                                  ~/.openerp_serverrc.
  -d, --database TEXT             Specify the database name. If present, this
                                  parameter takes precedence over the database
                                  provided in the Odoo configuration file.
  --log-level TEXT                Specify the logging level. Accepted values
                                  depend on the Odoo version, and include
                                  debug, info, warn, error.  [default: warn]
  --logfile FILE                  Specify the log file.
  --rollback                      Rollback the transaction even if the script
                                  does not raise an exception. Note that if
                                  the script itself commits, this option has
                                  no effect. This is why it is not named dry
                                  run. This option is implied when an
                                  interactive console is started.
  --installed-addons-only / --include-all-addons
                                  Work with installed addons only (default) or
                                  include not installed addons
  --help                          Show this message and exit.

Commands:
  addon-why                   List modules that depend on the given module
  addons-python-dependencies  List python dependencies for the instance...
  generate-repos-yaml          Generate repos.yml file for git-aggregator.
  list-addons                 List addons and their status
```



#### odoo-instance generate-repos-yaml

Generate repos.yml file for git-aggregator. If your addons come from git repositories, this command will generate a repos.yml file for git-aggregate.

##### Usage

```
Usage: odoo-instance generate-repos-yaml [OPTIONS]

```
##### CLI Help

```
Usage: odoo-instance generate-repos-yaml [OPTIONS]

  Generate repos.yml file for git-aggregator. If your addons come from git
  repositories, this command will generate a repos.yml file for git-aggregate.

Options:
  -o, --output PATH  Output file for repos.yml
  --help             Show this message and exit.
```



#### odoo-instance list-addons

List addons and their status

##### Usage

```
Usage: odoo-instance list-addons [OPTIONS]

```
##### CLI Help

```
Usage: odoo-instance list-addons [OPTIONS]

  List addons and their status

Options:
  --minimize-list           Minimize the list of addons (to install) with the
                            game of dependencies
  --format [flat|json|csv]
  --help                    Show this message and exit.
```



#### odoo-instance addon-why

List modules that depend on the given module

##### Usage

```
Usage: odoo-instance addon-why [OPTIONS] ADDON_NAME

```
##### CLI Help

```
Usage: odoo-instance addon-why [OPTIONS] ADDON_NAME

  List modules that depend on the given module

Options:
  --help  Show this message and exit.
```



#### odoo-instance addons-python-dependencies

List python dependencies for the instance addons

##### Usage

```
Usage: odoo-instance addons-python-dependencies [OPTIONS]

```
##### CLI Help

```
Usage: odoo-instance addons-python-dependencies [OPTIONS]

  List python dependencies for the instance addons

Options:
  --help  Show this message and exit.
```

##### CLI Help

```
Usage: odoo-instance list-addons [OPTIONS]

  List addons and their status

Options:
  --format [flat|json|csv]
  --help                    Show this message and exit.
```




### Development

TODO


### TODO

- add other subcommands
- add tests

- Refactor the cli layout to get a stuff like: \
    odoo-instance addon why addon_name \
    odoo-instance addons python-dependencies \

### License

This project is licensed under the AGPL 3 License. See the `LICENSE` file for details.

### Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

For any questions or suggestions, please open an issue or contact the maintainers.
