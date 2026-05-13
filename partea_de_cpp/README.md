Trebuie incarcat pe Pi si compilat acolo

cam ceva de genul pe linux:
rsync -avz --delete /LOCAL/PATH/ USER@PI_IP:/REMOTE/PATH/

pe Windows ideal e WSL dar cred ca merge si ceva de genul asta
scp -r /c/Users/YourName/Proiecte/Magna parcarelaterala@192.168.1.3:~/CPP/

inlocuiest ip-ul si path-ul cu cele reale

Dupa ce l-ai uploadat, te asiguri ca te afli in folderul corect si rulezi
./scripts/build.sh

apoi 
./scripts/run.sh
