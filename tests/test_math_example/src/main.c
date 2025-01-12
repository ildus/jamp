#include <stdio.h>
#include <math.h>
#include "common.h"

int
main()
{
    const double val = 42.0;
    char         buf[100];
    (void) snprintf(buf, sizeof(buf), "%f", sqrt(val * val));
    print_something(buf);
}
