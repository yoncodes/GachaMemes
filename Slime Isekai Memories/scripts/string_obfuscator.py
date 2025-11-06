from typing import List, Union
import base64


class I2_Loc_StringObfucator:
    StringObfuscatorPassword: bytes
    pw_generated: bool = False

    @staticmethod
    def FromBase64(param_1: str) -> bytes:
        return base64.b64decode(param_1)

    @staticmethod
    def ToBase64(param_1: bytes) -> str:
        return base64.b64encode(param_1)

    @staticmethod
    def Decode(param_1: str) -> bytes:
        param_1 = I2_Loc_StringObfucator.FromBase64(param_1)
        return I2_Loc_StringObfucator.XoREncode(param_1)

    @staticmethod
    def Encode(param_1: bytes) -> str:
        param_1 = I2_Loc_StringObfucator.XoREncode(param_1)
        return I2_Loc_StringObfucator.ToBase64(param_1)

    @staticmethod
    def XoREncode(buffer: bytearray) -> bytes:
        if isinstance(buffer, bytes):
            buffer = bytearray(buffer)

        # pass = StringObfuscatorPassword
        # buffer = NormalString.ToCharArray();
        pw = "ÝúbUu¸CÁÂ§*4PÚ©-á©¾@T6Dl±ÒWâuzÅm4GÐóØ$=Íg,¥Që®iKEßr¡×60Ít4öÃ~^«y:Èd1<QÛÝúbUu¸CÁÂ§*4PÚ©-á©¾@T6Dl±ÒWâuzÅm4GÐóØ$=Íg,¥Që®iKEßr¡×60Ít4öÃ~^«y:Èd".encode()
        passlen = len(pw)

        for i in range(len(buffer)):
            buffer[i] = (
                buffer[i] ^ pw[i % passlen] ^ (i * 23 if i % 2 == 0 else -i * 51) % 256
            )

        return buffer

    @staticmethod
    def XoREncode_rev(param_1: bytes) -> bytes:
        # if ((DAT_06c0f55f & 1) == 0) {
        #   thunk_FUN_01323f44(&DAT_06a35578);
        #   DAT_06c0f55f = 1;
        # }
        if not I2_Loc_StringObfucator.pw_generated:
            I2_Loc_StringObfucator.generate_pw()

        # lVar9 = **(long **)(DAT_06a35578 + 0xb8); # has to have some values other than 0
        lVar9 = I2_Loc_StringObfucator.StringObfuscatorPassword[
            0xB8:
        ]  # maybe w/o [0xb8:], could just be a struct offset
        # lVar4 = System.String.ToCharArray(param_1,0);
        lVar4 = bytearray(param_1)

        # if (0 < (int)*(ulong *)(lVar4 + 0x18)) {
        if 0 < lVar4[0x18]:
            # iVar1 = *(int *)(lVar9 + 0x18);
            iVar1 = lVar9[0x18]
            # uVar7 = *(ulong *)(lVar4 + 0x18) & 0xffffffff; # & shouldn't do anything.....
            uVar7 = lVar4[0x18] & 0xFFFFFFFF
            uVar6 = 0
            while True:
                if uVar7 <= uVar6:
                    # try { // try from 023023d4 to 023023df has its CatchHandler @ 02302408 */
                    # uVar5 = thunk_FUN_0131bf30();
                    # /* WARNING: Subroutine does not return */
                    # FUN_0136baa4(uVar5,0);
                    raise NotImplementedError()

                iVar3 = uVar6 // iVar1 if iVar1 else 0
                uVar2 = uVar6 - iVar3 * iVar1

                # if (*(uint *)(lVar9 + 0x18) <= uVar2) {
                if lVar9[0x18] <= uVar2:
                    # /* try { // try from 023023e0 to 023023eb has its CatchHandler @ 02302404 */
                    # uVar5 = thunk_FUN_0131bf30();
                    # /* WARNING: Subroutine does not return */
                    # FUN_0136baa4(uVar5,0);
                    # }
                    raise NotImplementedError()

                sVar8 = (0xFFFF - 0x33) if uVar6 & 1 else 0x17
                # *(ushort *)(lVar4 + 0x20 + uVar6 * 2) =
                #      *(ushort *)(lVar9 + (long)(int)uVar2 * 2 + 0x20) ^
                #      *(ushort *)(lVar4 + 0x20 + uVar6 * 2) ^ sVar8 * (short)uVar6 & 0xffU;
                lVar4[0x20 + uVar6 * 2 : 0x22 + uVar6 * 2] = ushort_xor(
                    lVar9[uVar2 * 2 + 0x20 : uVar2 * 2 + 0x22],
                    lVar4[0x20 + uVar6 * 2 : 0x22 + uVar6 * 2],
                    sVar8 * uVar6 & 0xFF,
                )
                uVar6 += 1
                uVar6 = uVar6 + 1
                if not (uVar6 < uVar7):
                    break


def ushort_xor(*args: List[Union[bytearray, int]]) -> bytearray:
    ret = bytearray(2)
    for arg in args:
        if isinstance(arg, int):
            arg = arg.to_bytes(2, "big", signed=False)
        ret[0] ^= arg[0]
        ret[1] ^= arg[1]
    return ret

