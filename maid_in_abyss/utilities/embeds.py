import disnake

__all__ = ("FormattableEmbed",)


class FormattableEmbed(disnake.Embed):
    def format(self, **format_map: object):
        sub_key: object
        sub_value: object
        embed = self.copy()

        for key in self.__slots__:
            if isinstance(value := getattr(embed, key), str):
                setattr(embed, key, value.format_map(format_map))

            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, str):
                        value[sub_key] = sub_value.format_map(format_map)

        if not embed._fields:
            return embed

        for field in embed._fields:
            for key, value in field.items():
                if isinstance(value, str):
                    field[key] = value.format_map(format_map)

        return embed
