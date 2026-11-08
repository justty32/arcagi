/* Minimal C solver for the arcagi file protocol (C99, no libraries).
 *
 * Build: cc -std=c99 -O2 -o solver solver.c
 * Usage: ./solver REQUEST.json RESPONSE.json [TRACE.json]
 * Experiment argv: ["./solver", "{input}", "{output}", "{trace}"]
 *
 * It copies each test input as the prediction (a protocol demo, not a solver).
 * The tiny scanner below only understands what it needs from the request:
 * the "task_id" string and the grids under "task" -> "test" -> "input".
 * Real solvers should use a proper JSON library.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *read_file(const char *path) {
    FILE *file = fopen(path, "rb");
    if (!file) return NULL;
    fseek(file, 0, SEEK_END);
    long size = ftell(file);
    rewind(file);
    char *data = malloc((size_t)size + 1);
    if (!data || fread(data, 1, (size_t)size, file) != (size_t)size) {
        fclose(file);
        free(data);
        return NULL;
    }
    data[size] = '\0';
    fclose(file);
    return data;
}

/* Return the position just after `"key"` and the following ':' (or NULL). */
static const char *after_key(const char *from, const char *key) {
    char pattern[64];
    snprintf(pattern, sizeof pattern, "\"%s\"", key);
    const char *found = strstr(from, pattern);
    if (!found) return NULL;
    found = strchr(found + strlen(pattern), ':');
    return found ? found + 1 : NULL;
}

/* Copy one JSON array of integers/arrays starting at '[' to `out`. */
static const char *copy_array(const char *p, FILE *out) {
    int depth = 0;
    do {
        if (*p == '\0') return NULL;
        if (*p == '[') depth++;
        if (*p == ']') depth--;
        if (*p != ' ' && *p != '\n' && *p != '\r' && *p != '\t') fputc(*p, out);
        p++;
    } while (depth > 0);
    return p;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s REQUEST.json RESPONSE.json [TRACE.json]\n", argv[0]);
        return 2;
    }
    char *request = read_file(argv[1]);
    if (!request) {
        perror(argv[1]);
        return 1;
    }
    const char *id = after_key(request, "task_id");
    const char *task = after_key(request, "task");
    const char *test = task ? after_key(task, "test") : NULL;
    if (!id || !test || !(id = strchr(id, '"'))) {
        fprintf(stderr, "request is missing task_id or task.test\n");
        return 1;
    }
    const char *id_end = strchr(id + 1, '"');
    FILE *out = fopen(argv[2], "w");
    if (!out || !id_end) {
        perror(argv[2]);
        return 1;
    }
    fprintf(out, "{\"%.*s\": [", (int)(id_end - id - 1), id + 1);
    const char *p = strchr(test, '[') + 1; /* the list of {"input": GRID} */
    int count = 0;
    while ((p = strchr(p, '{')) != NULL) {
        const char *grid = after_key(p, "input");
        if (!grid || !(grid = strchr(grid, '['))) break;
        if (count++) fputs(", ", out);
        p = copy_array(grid, out);
        if (!p) break;
        p = strchr(p, '}');
        if (!p) break;
        p++;
        while (*p == ' ' || *p == ',' || *p == '\n') p++;
        if (*p == ']') break; /* end of the test list */
    }
    fputs("]}\n", out);
    fclose(out);
    free(request);

    if (argc > 3) {
        FILE *trace = fopen(argv[3], "w");
        if (trace) {
            fprintf(trace,
                    "{\"schema_version\": \"arcagi-trace/1\", \"solver\": \"c_identity\", "
                    "\"attempts\": [{\"id\": \"copy\", \"kind\": \"program\", "
                    "\"program\": \"identity\", \"description\": \"copy test inputs\", "
                    "\"selected\": true}], \"selected\": \"copy\", "
                    "\"reasoning\": \"Demo only: training pairs are not checked.\"}\n");
            fclose(trace);
        }
    }
    return count > 0 ? 0 : 1;
}
