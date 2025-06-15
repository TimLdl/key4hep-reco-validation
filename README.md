# Key4hep Reco Validation Workflow

This repository hosts workflow which runs Key4hep reco validation chain, which
can be found [here](https://github.com/key4hep/key4hep-reco-validation).

## Running locally

* Install [gitlab-ci-local](https://github.com/firecow/gitlab-ci-local)
* In the directory where `.gitlab-ci.yml` run
    ```sh
    gitlab-ci-local --list-all
    ```
  to see all jobs.
* To run one of the jobs without the need for Docker, adjust `WORKAREA` variable
    and run
    ```sh
    gitlab-ci-local --force-shell-executor execute_scripts
    ```
