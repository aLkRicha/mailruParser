## Installation:
```
virtualenv env -p $(which python2.7) --no-wheel --no-setuptools
env/bin/pip install -r requirements.txt  
```

Download and place binary from archive to bin folder - http://phantomjs.org/download.html


## Usage
run parser worker
```
env/bin/python test.py --gearman_host example.tld
--debug  - for console log
--chrome - for using Chrome webdriver instead of PhantomJS
```

Next, send to your gearman server task to `parseFriends` and as data send json with same structure:
```json
{
	"auth": {
		"login": "someUser@mail.ru",
		"password": "somePassword.ru"
	},
	"users": [
		{
			"email": "violetta55@mail.ru"
		},
		{
			"email": "naira_khachatryan_1994@mail.ru"
		}
	]
}
```

parser will return json with emails.