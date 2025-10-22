import logging
from pathlib import Path
from google.protobuf.descriptor_pb2 import FileDescriptorSet

log = logging.getLogger(__name__)

class ProtoBuilder:
    """
    Builds .proto files from a protobuf FileDescriptorSet (usually 'moon.pb').
    """

    # ------------------------------------------------------------------ #
    def build_from_file(self, pb_path, output_dir="proto/generated"):
        """Read a .pb file from disk and build .proto files."""
        pb_path = Path(pb_path)
        if not pb_path.exists():
            log.error(f"ProtoBuilder: {pb_path} not found.")
            return None

        with open(pb_path, "rb") as f:
            data = f.read()

        log.info(f"Building .proto files from {pb_path} ({len(data)} bytes)...")
        return self.build_from_bytes(data, output_dir)

    # ------------------------------------------------------------------ #
    def build_from_bytes(self, proto_bytes, output_dir="proto/generated"):
        """Parse protobuf descriptor and save individual .proto files."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        log.info(f"[+] Created output directory: {output_dir}")

        fds = FileDescriptorSet()
        fds.ParseFromString(proto_bytes)
        log.info(f"[+] Found {len(fds.file)} proto file(s)\n")

        for file_desc in fds.file:
            file_path = file_desc.name or "unknown.proto"
            package = file_desc.package or "(no package)"

            log.info(f"{'='*60}")
            log.info(f"File: {file_path}")
            log.info(f"Package: {package}")
            log.info(f"{'='*60}\n")

            proto_content = self._generate_proto_file(file_desc)

            full_path = output_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(proto_content)

            log.info(f"[+] Saved: {full_path}")
            log.info(f"    Messages: {len(file_desc.message_type)}")
            log.info(f"    Enums: {len(file_desc.enum_type)}\n")

        log.info(f"[✓] All proto files saved to {output_dir}/")
        return fds

    # ------------------------------------------------------------------ #
    def _generate_proto_file(self, file_desc):
        lines = ['syntax = "proto3";', '']

        if file_desc.package:
            lines.append(f'package {file_desc.package};')
            lines.append('')

        for dep in file_desc.dependency:
            lines.append(f'import "{dep}";')
        if file_desc.dependency:
            lines.append('')

        for enum in file_desc.enum_type:
            lines.extend(self._generate_enum(enum, 0))
            lines.append('')

        for msg in file_desc.message_type:
            lines.extend(self._generate_message(msg, 0))
            lines.append('')

        return '\n'.join(lines)

    # ------------------------------------------------------------------ #
    def _generate_message(self, msg_desc, indent_level):
        indent = '  ' * indent_level
        lines = [f'{indent}message {msg_desc.name} {{']

        for enum in msg_desc.enum_type:
            lines.extend(self._generate_enum(enum, indent_level + 1))
            lines.append('')

        for nested in msg_desc.nested_type:
            lines.extend(self._generate_message(nested, indent_level + 1))
            lines.append('')

        for field in msg_desc.field:
            field_line = f'{indent}  '
            if field.label == 3:  # repeated
                field_line += 'repeated '

            field_type = self._get_field_type(field)
            field_line += f'{field_type} {field.name} = {field.number};'
            lines.append(field_line)

        lines.append(f'{indent}}}')
        return lines

    # ------------------------------------------------------------------ #
    def _generate_enum(self, enum_desc, indent_level):
        indent = '  ' * indent_level
        lines = [f'{indent}enum {enum_desc.name} {{']
        for value in enum_desc.value:
            lines.append(f'{indent}  {value.name} = {value.number};')
        lines.append(f'{indent}}}')
        return lines

    # ------------------------------------------------------------------ #
    def _get_field_type(self, field):
        type_map = {
            1: 'double', 2: 'float', 3: 'int64', 4: 'uint64', 5: 'int32',
            6: 'fixed64', 7: 'fixed32', 8: 'bool', 9: 'string', 12: 'bytes',
            13: 'uint32', 15: 'sfixed32', 16: 'sfixed64', 17: 'sint32', 18: 'sint64',
        }
        if field.type in [11, 14]:  # message or enum
            return field.type_name.split('.')[-1]
        return type_map.get(field.type, f'unknown_type_{field.type}')
