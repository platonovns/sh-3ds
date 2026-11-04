"""Only replace the pure leading-zero helper; no GTE register/order changes."""
from pathlib import Path
PORT=Path(__file__).resolve().parents[1]

def prepare():
    source=(PORT/'build/psycross/src/gte/PsyX_GTE.cpp').read_text()
    start=source.index('unsigned int gte_leadingzerocount(')
    end=source.index('\nint LIM(',start)
    before=source[start:end]
    after='''unsigned int gte_leadingzerocount(unsigned int value)
{
    // Guard zero: __builtin_clz(0) is undefined, the original helper returns 32.
    return value ? (unsigned)__builtin_clz(value) : 32u;
}
'''
    dest=PORT/'build/stage11a-cpu/PsyX_GTE.cpp';dest.parent.mkdir(exist_ok=True)
    dest.write_text(source[:start]+after+source[end:])
    return dest,before,after

if __name__=='__main__':print(prepare()[0])
