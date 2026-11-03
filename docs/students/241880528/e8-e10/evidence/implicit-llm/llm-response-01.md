```makefile
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
```

修改原因：

1. **动态依赖跟踪**：在编译规则中加入 `-MMD -MP`。
   - `-MMD` 让 GCC 在编译每个 `.c` 时同时生成对应的 `.d` 文件，其中记录该目标文件实际依赖的项目内头文件（如 `main.o: main.c config.h`）。
   - `-MP` 为每个头文件生成空的伪目标规则，避免头文件被删除/重命名后 make 因找不到依赖而报错。

2. **引入 `.d` 文件并包含**：新增 `DEPS = $(OBJS:.o=.d)`，并用 `-include $(DEPS)` 包含这些依赖文件。
   - 使用 `-include`（而非 `include`）是为了首次构建时 `.d` 文件尚不存在也不报错。
   - 这样 `main.o` 对 `config.h` 的缺失依赖会由生成的 `.d` 文件自动补全，无需在 Makefile 中逐个硬编码头文件依赖，`helper.o` 等其他目标也同样受益。

3. **保持原有风格**：保留 `CC`、`CFLAGS`、`OBJS` 变量和 `%.o: %.c` 模式规则，默认目标仍为 `app`，编译选项 `-O0` 不变，仅在编译命令上追加依赖生成选项。

4. **clean 清理新增文件**：在 `clean` 中加入 `$(DEPS)`，使 `.d` 文件也被清除。

说明：以上修改依据缺失依赖报告和 GNU Make 的常规做法编写，候选方案尚未实际构建验证，请以实际运行 `make` 的结果为准。
