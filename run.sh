docker build -t unciv-mailer . || exit 1
docker rm $(docker stop unciv-mailer 2>/dev/null) 2>/dev/null
docker run -d\
	--restart always\
	-v ./config:/config\
	-v unciv-volume:/Unciv:ro\
	--name unciv-mailer\
	--env-file=run.env\
	unciv-mailer
