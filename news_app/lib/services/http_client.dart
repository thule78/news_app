import 'dart:convert';
import 'dart:io';

import '../core/constants/app_constants.dart';
import '../core/utils/result.dart';

class AppHttpClient {
  final HttpClient _client = HttpClient()
    ..connectionTimeout = const Duration(seconds: 15);

  Future<Result<Map<String, dynamic>>> getJson(String path) async {
    try {
      final uri = Uri.parse('${AppConstants.apiBaseUrl}$path');
      final request = await _client.getUrl(uri);
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      final response = await request.close();
      final responseBody = await response.transform(utf8.decoder).join();

      if (response.statusCode < 200 || response.statusCode >= 300) {
        return Result.failure('Request failed (${response.statusCode}).');
      }

      final decoded = jsonDecode(responseBody);
      if (decoded is! Map<String, dynamic>) {
        return Result.failure('Invalid response shape.');
      }
      return Result.success(decoded);
    } catch (_) {
      return Result.failure('Network request failed.');
    }
  }

  void dispose() {
    _client.close(force: true);
  }
}
