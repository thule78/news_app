class DateFormatters {
  static String shortDate(String? raw) {
    if (raw == null || raw.isEmpty) return '--';
    final date = DateTime.tryParse(raw);
    if (date == null) return raw;
    return '${date.day.toString().padLeft(2, '0')}/'
        '${date.month.toString().padLeft(2, '0')}/${date.year}';
  }
}
