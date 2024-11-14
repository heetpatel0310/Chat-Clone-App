all: scraper

scraper: scraper.c
	clang scraper.c -o scraper

clean:  
	rm -f scraper