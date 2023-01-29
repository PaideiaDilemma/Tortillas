[ "$#" -eq 2 ] || die "usage: setup_sweb.sh <tortillas_path> <sweb_path>"

tortillas_path=$1
sweb_path=$2

git -C $sweb_path apply --ignore-whitespace $tortillas_path/sweb_patches/*.diff

cp $tortillas_path/tortillas_config.yml $sweb_path/
