Cread
=====

C-READ customization for GeoNode

Installation
------------

Install geonode with::

    $ sudo add-apt-repository ppa:geonode/testing

    $ sudo apt-get update

    $ sudo apt-get install geonode


Usage
-----

Rename the local_settings.py.sample to local_settings.py and edit its content by setting the SITEURL and SITENAME.

Edit the file /etc/apache2/sites-available/geonode and change the following directive from:

    WSGIScriptAlias / /var/www/geonode/wsgi/geonode.wsgi

to:

    WSGIScriptAlias / /path/to/my_geonode/my_geonode/wsgi.py

Add the "Directory" directive for your folder like the following example:

    <Directory "/home/vagrant/my_geonode/my_geonode/">

       Order allow,deny

       Options Indexes FollowSymLinks

       Allow from all

       Require all granted

       IndexOptions FancyIndexing
       
    </Directory>

Restart apache::

    $ sudo service apache2 restart

Edit the templates in cread/templates, the css and images to match your needs.

In the cread folder run::

    $ python manage.py collectstatic


