#!/bin/bash
[ "$#" -eq 3 ] || die "usage: setup_sweb.sh <tortillas_path> <sweb_path> <example>"

tortillas_path=$1
sweb_path=$2
example_dir="$tortillas_path/examples/$3"

git -C $sweb_path apply --ignore-whitespace $tortillas_path/examples/common_sweb_patches/*.diff

if [ -d "$example_dir/sweb_patches" ]; then
    git -C $sweb_path apply --ignore-whitespace $example_dir/sweb_patches/*.diff
fi

cp $example_dir/tortillas_config.yml $sweb_path/
