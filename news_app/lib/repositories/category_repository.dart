import '../core/utils/result.dart';
import '../models/category_model.dart';
import '../services/api_endpoints.dart';
import '../services/http_client.dart';

class CategoryRepository {
  CategoryRepository(this._httpClient);

  final AppHttpClient _httpClient;

  Future<Result<List<CategoryModel>>> fetchCategories() async {
    final response = await _httpClient.getJson(ApiEndpoints.categories);
    if (!response.isSuccess || response.data == null) {
      return Result.failure(response.error ?? 'Unable to load categories.');
    }

    final data = response.data!['data'];
    if (data is! List) {
      return Result.failure('Invalid categories payload.');
    }

    final categories = data
        .whereType<Map<String, dynamic>>()
        .map(CategoryModel.fromJson)
        .toList(growable: false);
    return Result.success(categories);
  }
}
