#!/bin/bash
# Install and configure wxstation
# Created by Steven Fairchild on 20210407

# Print usage message
usage() {
    echo -e "Script usage\n\
    \t--database-only - Setup database only\n\
    \t--pkgs-only - Install debian and python packages only\n\
    \t--skip-database - Skip database install and setup\n\
    \t--help - Print this message\n"
}

red="\033[0;31m"
creset="\033[0m"

check_root() {
    if [[ "$(whoami)" != "root" ]]; then
        echo -e "\n${red}This script must be ran as root user or with sudo!"
        echo -e "Exiting...\n${creset}"
        usage
        exit 0
    else
        clear
    fi
}

# Create user service account and service
create_user() {
    grep ${service_account} /etc/passwd > /dev/null
    if [[ "$?" != "0" ]]; then
        useradd -m -d ${service_dir} -c "wxstation service account" -r ${service_account}
        usermod -aG ${service_groups} ${service_account}
    fi
}

install_pkgs() {
    echo "Attempting to install required packages now"
    if [[ ! -z ${deb_pkgs} ]]; then
        echo "Installing debian packages..."
        apt install ${deb_pkgs} -y
    fi
    if [[ ! -z ${py_pkgs} ]]; then
        echo "Installing python packages..."
        pip3 install ${py_pkgs}
    fi
}

# Create and setup mariadb
setup_db() {
    if [[ -f /etc/init.d/mysql ]]; then
        /etc/init.d/mysql start
    elif [[ -f /etc/systemd/system/mysql.service ]] || [[ -f /usr/lib/systemd/system/mysql.service ]]; then
        systemctl enable --now mysql.service
    elif [[ -f /etc/systemd/system/mariadb-server.service ]] || [[ -f /usr/lib/systemd/system/mariadb-server.service ]]; then
        systemctl enable --now mariadb-server.service
    fi
    printf "Creating $db_name database\n"
    mysql -e "CREATE DATABASE IF NOT EXISTS $db_name;"
    echo "creating $db_user in mariadb"
    mysql -e "CREATE USER IF NOT EXISTS '$db_user'@localhost IDENTIFIED BY '$db_userpass';"
    echo "Securing mariadb root account"
    mysql -e "UPDATE mysql.user SET Password = PASSWORD('$root_password') WHERE User = 'root'"
    mysql -e "GRANT ALL PRIVILEGES ON \`$db_name\`.* TO '$db_user'@localhost;"
    mysql -e "FLUSH PRIVILEGES;"
    echo "Creating sensors table in ${db_name} database"
    mysql -e "CREATE TABLE IF NOT EXISTS ${db_name}.sensors(\
            ID BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,\
            stationid VARCHAR(10),\
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\
            ambient_temperature DECIMAL(6,2) NOT NULL,\
            wind_direction SMALLINT,\
            wind_speed DECIMAL(6,2),\
            wind_gust_speed DECIMAL(6,2),\
            humidity DECIMAL(6,2) NOT NULL,\
            rainfall DECIMAL(6,3),\
            air_pressure DECIMAL(6,2) NOT NULL,\
            PM25 DECIMAL(6,2),\
            PM10 DECIMAL(6,2));"

    echo "Creating packet table in ${db_name} database"
    mysql -e "CREATE TABLE IF NOT EXISTS ${db_name}.packets(\
            ID BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,\
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\
            packet VARCHAR(82) NOT NULL,\
            transmitted BOOL NOT NULL);"
}
systemd_setup() {
    if [[ -d /usr/lib/systemd/system ]]; then
    echo -e "[Unit]\n\
Description=Wxstation Service\n\
After=network.target\n\

[Service]\n\
Type=simple\n\
User=wxstation\n\
WorkingDirectory=${service_dir}/bin\n\
Environment=PYTHONPATH=${service_dir}/bin\n\
ExecStart=/usr/bin/python3 -u ${service_dir}/bin/main.py\n\
Restart=on-failure\n\

[Install]\n\
WantedBy=multi-user.target" > /usr/lib/systemd/system/wxstation.service
    systemctl daemon-reload
    systemctl enable wxstation.service
    else
        echo "Unable to install wxstation.service, directory /usr/lib/systemd/system does not exist"
    fi
}
rclocal_install() {
    if [[ -d /usr/lib/systemd/system ]]; then
    echo -e "[Unit]\n\
Description=/etc/rc.local\n\
ConditionPathExists=/etc/rc.local\n\

[Service]\n\
Type=forking\n\
ExecStart=/etc/rc.local start\n\
TimeoutSec=0\n\
StandardOutput=tty\n\
RemainAfterExit=yes\n\
SysVStartPriority=99\n\

[Install]\n\
WantedBy=multi-user.target" > /usr/lib/systemd/system/rc-local.service
    echo "Installed wxstation.service systemd-unit"
    systemctl daemon-reload
    systemctl enable rc-local.service
    else
        echo "Unable to install wxstation.service, directory /usr/lib/systemd/system does not exist"
    fi
}
rclocal_setup() {
    echo -e "echo none > /sys/class/leds/led0/trigger\n\
    echo none > /sys/class/leds/led1/trigger\n\
    echo 0 > /sys/class/leds/led0/brightness\n\
    echo 0 > /sys/class/leds/led1/brightness\n\
    echo tvservice -o\n\
    exit0" >> /etc/rc.local
    echo "LEDs set to disabled on boot in /etc/rc.local"
}

disable_leds() {
    lscpu | grep ^Model\ name: | grep Broadcom\ BCM 2>&1 >> /dev/null
    if [[ "$?" -eq 0 ]]; then
        echo "Running on raspberry pi, disabling LEDs..."
        echo none > /sys/class/leds/led0/trigger
        echo none > /sys/class/leds/led1/trigger
        echo 0 > /sys/class/leds/led0/brightness
        echo 0 > /sys/class/leds/led1/brightness
        if [[ -f "$(which tvservice)" ]]; then
            tvservice -o
            echo "Disabled HDMI port"
        fi
        if [[ ! -f /etc/systemd/system/multi-user.target.wants/rc-local.service ]] || [[ ! -f /usr/lib/systemd/system/rc-local.service ]]; then
            echo "Installing and enabling rc-local.service"
            rclocal_install
        fi
        echo "Setting LEDs to disabled on boot in /etc/rc.local"
        if [[ -f /etc/rc.local ]]; then
            grep /sys/class/leds/led0/trigger /etc/rc.local
            if [[ ! "$?" -eq 0 ]]; then
                rclocal_setup
            else
                echo "/etc/rc.local has already been edited, not modifying."
            fi
        else
            echo "/etc/rc.local does not exist. Creating file."
            rclocal_setup
        fi
    fi
}

copy_files() {
    cd ..
    mkdir -p ${service_dir}
    if [[ -d ${service_dir} ]]; then
        cp ./*.py ${service_dir}
        if [[ -f "${service_dir}/wxstation.yaml" ]]; then
            mv ${service_dir}/wxstation.yaml ${service_dir}/wxstation.yaml.save
            echo -e "${service_dir}/wxstation.yaml already exists, \
            creating backup at ${service_dir}/wxstation.yaml.save\n\
            Copy custom settings as needed."
        cp ./wxstation.yaml ${service_dir}/
        chown -R ${service_account}:${service_account} ${service_dir}
        cd -
    fi
    else
        echo "Unable to copy files to ${service_dir}, directory does not exist."
    fi
}

main() {
    if [[ -f setup_settings.env ]]; then
        source setup_settings.env
    else
        echo -e "setup_settings not found.\nAre you in the setup directory?\nExiting"; exit 1
    fi

    if [[ ! -z "${1}" ]] && [[ "${1}" != "--skip-database" ]]; then
        if [[ "${1}" == "--database-only" ]]; then
            echo "Setting up database only!"
            setup_db
            echo "Done setting up database!"
            exit 0
        elif [[ "${1}" == "--pkgs-only" ]]; then
            install_pkgs
            echo "Done installing packages!"
            echo "Exiting!"
            exit 0
        else
            usage
        fi
    else
        create_user
        if [[ "${1}" != "--skip-database" ]]; then
            install_pkgs
            setup_db
        else
            echo "Skipping database install and setup"
            export deb_pkgs=$(echo ${deb_pkgs} | sed 's/mariadb-server //g')
            install_pkgs
        fi
        disable_leds
        systemd_setup
        copy_files
        echo "All done!"
    fi
}

check_root
main "${1}"
exit 0
