#!/bin/bash

DIR="$1"

if [ -z "$DIR" ]; then
  echo "No directory provided."
  exit 1
fi
echo "Fixing permissions for: $DIR"

UNAME=$(uname)
if [[ "$UNAME" == "Darwin" || "$UNAME" == "Linux" ]]; then
  chmod -R u+rwX "$DIR"
  echo "Permissions granted for user (u+rwX)"

elif [[ "$UNAME" == *"MINGW"* || "$UNAME" == *"MSYS"* || "$UNAME" == *"CYGWIN"* ]]; then
  icacls "$DIR" /grant Everyone:F /T > /dev/null
  echo "Permissions granted for working folder"

else
  echo "Unsupported OS: $UNAME"
  exit 1
fi
