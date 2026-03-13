#!/bin/bash

# SecureLens File Transfer Script
# Usage: ./transfer_file.sh

echo "SecureLens File Transfer"
echo "======================="
echo "1. Copy file TO securelens-web container"
echo "2. Copy file FROM securelens-web container"
read -p "Select option (1-2): " option

case $option in
    1)
        read -p "Enter source file path (on host): " source_path
        if [[ ! -f "$source_path" ]]; then
            echo "Error: Source file does not exist"
            exit 1
        fi
        echo "Copying to container..."
        docker cp "$source_path" securelens-web-1:/opt
        echo "Done!"
        ;;
    2)
        read -p "Enter source file path in container: " source_path
        read -p "Enter destination path on host: " dest_path
        echo "Copying from container..."
        docker cp "securelens-web-1:$source_path" "$dest_path"
        echo "Done!"
        ;;
    *)
        echo "Invalid option"
        ;;
esac
