DEPS = main.c unused.h config.h
CFLAGS = -O0
app: main.o helper.o
	gcc main.o helper.o -o app
main.o: $(DEPS)
	gcc $(CFLAGS) -c main.c -o main.o
helper.o: helper.c
	gcc $(CFLAGS) -c helper.c -o helper.o
.PHONY: clean
clean:
	rm -f main.o helper.o app
