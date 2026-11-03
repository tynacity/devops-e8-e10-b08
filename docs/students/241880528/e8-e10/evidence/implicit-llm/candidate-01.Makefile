CC = gcc
CFLAGS = -O0
OBJS = main.o helper.o
DEPS = $(OBJS:.o=.d)

app: $(OBJS)
	$(CC) $(OBJS) -o $@

%.o: %.c
	$(CC) $(CFLAGS) -MMD -MP -c $< -o $@

-include $(DEPS)

.PHONY: clean
clean:
	rm -f $(OBJS) $(DEPS) app
