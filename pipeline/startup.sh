#! /bin/bash
sudo apt-get update -y; sudo apt install openjdk-17-jre-headless -y; sudo apt install unzip; sudo apt install screen -y; sudo apt install nano -y;
echo "eula=true" > eula.txt

wget https://piston-data.mojang.com/v1/objects/f69c284232d7c7580bd89a5a4931c3581eae1378/server.jar
java -Xms1024M -Xmx1024M -jar server.jar nogui