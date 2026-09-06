/*
 * A stub icuuc.dll, so that Qt6Core can be loaded where Windows' own ICU is
 * not available — under Wine and CrossOver, which implement no equivalent.
 *
 * Qt6Core in the PyQt6 wheel imports exactly eighteen symbols from icuuc.dll,
 * all of them from ICU's converter API, and Windows has shipped that DLL in
 * System32 since Windows 10 1703. The import is static, so the loader refuses
 * the whole library when it is missing, however little of it is wanted.
 *
 * This exports those eighteen and nothing else, and answers as ICU does when
 * it has no converter to offer: ucnv_open fails, the available list is empty.
 * Qt then falls back to the codecs it implements itself — UTF-8, UTF-16,
 * UTF-32, Latin-1 and the system locale — which is everything this
 * application reads or writes. What is lost is the long tail of legacy
 * encodings, Shift-JIS and the like, in file dialogs and text import.
 *
 * It is a compatibility shim, not an implementation. Nothing here converts
 * anything, and it has no business on a real Windows machine, where the
 * genuine DLL is present and better in every way.
 */

typedef int UErrorCode;
typedef int int32_t;
typedef signed char int8_t;
typedef unsigned short UChar;
typedef signed char UBool;

/* the code real ICU returns when it cannot open a converter by that name */
#define U_FILE_ACCESS_ERROR 4

#define EXPORT __declspec(dllexport)

static void fail(UErrorCode *status)
{
    if (status && *status <= 0)   /* do not overwrite an existing failure */
        *status = U_FILE_ACCESS_ERROR;
}

/* -- opening and naming: this is where Qt finds out there is nothing here -- */

EXPORT void *ucnv_open(const char *name, UErrorCode *status)
{
    (void)name;
    fail(status);
    return 0;
}

EXPORT int32_t ucnv_countAvailable(void)
{
    return 0;
}

EXPORT const char *ucnv_getAvailableName(int32_t n)
{
    (void)n;
    return 0;
}

EXPORT const char *ucnv_getStandardName(const char *name, const char *standard,
                                        UErrorCode *status)
{
    (void)name; (void)standard;
    fail(status);
    return 0;
}

EXPORT const char *ucnv_getName(const void *converter, UErrorCode *status)
{
    (void)converter;
    fail(status);
    return 0;
}

EXPORT void ucnv_close(void *converter)
{
    (void)converter;
}

/* -- everything below is only reachable through a converter that ucnv_open
      never hands out, so these exist to satisfy the loader ------------- */

EXPORT int8_t ucnv_getMaxCharSize(const void *converter)
{
    (void)converter;
    return 4;
}

EXPORT void ucnv_reset(void *converter)
{
    (void)converter;
}

EXPORT void ucnv_setFromUCallBack(void *converter, void *action,
                                  const void *context, void **oldAction,
                                  const void **oldContext, UErrorCode *status)
{
    (void)converter; (void)action; (void)context;
    if (oldAction) *oldAction = 0;
    if (oldContext) *oldContext = 0;
    fail(status);
}

EXPORT void ucnv_setToUCallBack(void *converter, void *action,
                                const void *context, void **oldAction,
                                const void **oldContext, UErrorCode *status)
{
    (void)converter; (void)action; (void)context;
    if (oldAction) *oldAction = 0;
    if (oldContext) *oldContext = 0;
    fail(status);
}

EXPORT void ucnv_getFromUCallBack(const void *converter, void **action,
                                  const void **context)
{
    (void)converter;
    if (action) *action = 0;
    if (context) *context = 0;
}

EXPORT void ucnv_getToUCallBack(const void *converter, void **action,
                                const void **context)
{
    (void)converter;
    if (action) *action = 0;
    if (context) *context = 0;
}

EXPORT void ucnv_fromUnicode(void *cnv, char **target, const char *targetLimit,
                             const UChar **source, const UChar *sourceLimit,
                             int32_t *offsets, UBool flush, UErrorCode *status)
{
    (void)cnv; (void)target; (void)targetLimit; (void)source;
    (void)sourceLimit; (void)offsets; (void)flush;
    fail(status);
}

EXPORT void ucnv_toUnicode(void *cnv, UChar **target, const UChar *targetLimit,
                           const char **source, const char *sourceLimit,
                           int32_t *offsets, UBool flush, UErrorCode *status)
{
    (void)cnv; (void)target; (void)targetLimit; (void)source;
    (void)sourceLimit; (void)offsets; (void)flush;
    fail(status);
}

EXPORT int32_t ucnv_fromUCountPending(const void *cnv, UErrorCode *status)
{
    (void)cnv;
    fail(status);
    return 0;
}

EXPORT int32_t ucnv_toUCountPending(const void *cnv, UErrorCode *status)
{
    (void)cnv;
    fail(status);
    return 0;
}

EXPORT void ucnv_cbFromUWriteUChars(void *args, const UChar **source,
                                    const UChar *sourceLimit,
                                    int32_t offsetIndex, UErrorCode *status)
{
    (void)args; (void)source; (void)sourceLimit; (void)offsetIndex;
    fail(status);
}

EXPORT void ucnv_cbToUWriteUChars(void *args, const UChar *source,
                                  int32_t length, int32_t offsetIndex,
                                  UErrorCode *status)
{
    (void)args; (void)source; (void)length; (void)offsetIndex;
    fail(status);
}
