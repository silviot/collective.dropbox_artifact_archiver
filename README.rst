Artifact archiver
=================

Travis-ci is awesome, but doesn't provide storage space for test artifacts.

This prototype wsgi server should be invoked in a .travis.yml::

    after_script:
      - cd parts/test
      - tar cvjf artifacts.tar.bz2 *
      - curl http://collective_artifacts.rr.nu/submit_artifacts   --form archive=@artifacts.tar.bz2 --form TRAVIS_JOB_ID=$TRAVIS_JOB_ID --form TRAVIS_BUILD_ID=$TRAVIS_BUILD_ID


and, for example, configured in apache like this::

    <VirtualHost *:80>

        ServerName collective_artifacts.rr.nu
        ServerAdmin silviot@gropen.net

        WSGIDaemonProcess arifacts.site user=collectiveartifacts processes=2 threads=4
        WSGIProcessGroup arifacts.site
        WSGIScriptAlias / /home/collectiveartifacts/collective.dropbox_artifact_archiver/server.py

        <Directory /home/collectiveartifacts/collective.dropbox_artifact_archiver/>
        Order allow,deny
        Allow from all
        </Directory>

    </VirtualHost>

It will store the artifacts in a per-job, per-variable-matrix folder.
On the travis side public urls of html and ogv files will show up.
