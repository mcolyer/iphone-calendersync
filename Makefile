all:
	gcc -o sync sync.c -I/usr/local/include -L/usr/local/lib -liphone -lplist `pkg-config glib-2.0 --libs --cflags` -g -Wall
