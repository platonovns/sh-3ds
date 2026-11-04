/* PSY-Q to PsyCross compatibility shim */
#ifndef _PSYQ_COMPAT_LIBGTE_H
#define _PSYQ_COMPAT_LIBGTE_H
#include <libgte.h>

/* SquareRoot12: not in PsyCross, implemented in pc_port/src/math_impl.c */
extern int SquareRoot12(int a);
#ifdef SH_3DS_PORT
extern void ReadLightMatrix(MATRIX *m);
extern void OuterProduct12(VECTOR *v0, VECTOR *v1, VECTOR *v2);
extern long Lzc(long data);
extern void LoadAverageCol(const unsigned char *v0, const unsigned char *v1, long p0, long p1, unsigned char *v2);
extern long VectorNormal(const VECTOR *v0, VECTOR *v1);
extern MATRIX *TransposeMatrix(MATRIX *in, MATRIX *out);
extern VECTOR *Square0(VECTOR *in, VECTOR *out);
#endif
#endif
