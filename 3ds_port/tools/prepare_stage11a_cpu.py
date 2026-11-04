"""CPU checkpoint after F1. Frozen and the first F1 package stay untouched."""
from pathlib import Path
from prepare_stage11a_tracefix import prepare as prepare_f1


def prepare(dest):
    dest = prepare_f1(dest)
    file = dest / 'PsyX_SPUCore.cpp'
    text = file.read_text()
    before = '''    for (int i = 0; i < kAdpcmBlockSamples; ++i)
    {
        uint8_t byte = block[2 + (i >> 1)];
        int nibble = (i & 1) ? (byte >> 4) : (byte & 0xF);
        int32_t t = static_cast<int16_t>(nibble << 12); // sign-extend the 4bit nibble into bit15
        int32_t sample = t >> shift;
        sample += ((hist1 * f0 + hist2 * f1) >> 6);
        sample = SaturateS16(sample);

        v.blockSamples[i] = static_cast<int16_t>(sample);
        hist2 = hist1;
        hist1 = sample;
    }'''
    after = '''    // Consume both nibbles from one byte. Keep the serial predictor and
    // saturation between samples; the second predictor uses the first result.
    for (int i = 0; i < kAdpcmBlockSamples; i += 2)
    {
        const uint8_t byte = block[2 + (i >> 1)];
        const int32_t low = static_cast<int16_t>((byte & 15) << 12) >> shift;
        const int32_t high = static_cast<int16_t>((byte >> 4) << 12) >> shift;
        int32_t a = SaturateS16(low + ((hist1 * f0 + hist2 * f1) >> 6));
        int32_t b = SaturateS16(high + ((a * f0 + hist1 * f1) >> 6));
        v.blockSamples[i] = static_cast<int16_t>(a);
        v.blockSamples[i + 1] = static_cast<int16_t>(b);
        hist2 = a; hist1 = b;
    }'''
    assert text.count(before) == 1
    text = text.replace(before, after)
    # ARM11 has signed saturation. This is exactly the int32 -> int16 clamp;
    # no rounding, mixing width or interpolation arithmetic is changed.
    anchor = '''    if (v > 32767)  return 32767;
    if (v < -32768) return -32768;
    return static_cast<int16_t>(v);'''
    assert text.count(anchor) == 1
    text = text.replace(anchor, '''#if defined(__arm__)
    return static_cast<int16_t>(__builtin_arm_ssat(v, 16));
#else
''' + anchor + '\n#endif')
    file.write_text(text)
    return dest


if __name__ == '__main__':
    print(prepare(Path(__file__).resolve().parents[1] / 'build/stage11a-cpu/audio'))
