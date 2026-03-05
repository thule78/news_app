import '../core/utils/result.dart';
import '../models/article_detail_model.dart';
import '../models/article_model.dart';
import '../services/api_endpoints.dart';
import '../services/http_client.dart';

class ArticleRepository {
  ArticleRepository(this._httpClient);

  final AppHttpClient _httpClient;

  Future<Result<List<ArticleModel>>> fetchPopular({required int limit}) async {
    final response = await _httpClient.getJson(ApiEndpoints.popular(limit));
    return _parseArticleList(response);
  }

  Future<Result<List<ArticleModel>>> fetchByCategory({
    required int categoryId,
    required int page,
  }) async {
    final response = await _httpClient.getJson(
      ApiEndpoints.categoryArticles(categoryId, page),
    );
    return _parseArticleList(response);
  }

  Future<Result<ArticleDetailModel>> fetchDetail(int id) async {
    final response = await _httpClient.getJson(ApiEndpoints.articleDetail(id));
    if (!response.isSuccess || response.data == null) {
      return Result.failure(response.error ?? 'Unable to load article detail.');
    }

    final data = response.data!['data'];
    if (data is! Map<String, dynamic>) {
      return Result.failure('Invalid detail payload.');
    }
    return Result.success(ArticleDetailModel.fromJson(data));
  }

  Future<Result<List<ArticleModel>>> searchArticles(String keyword) async {
    if (keyword.trim().isEmpty) {
      return Result.success(<ArticleModel>[]);
    }

    final serverResponse = await _httpClient.getJson(
      ApiEndpoints.search(keyword.trim()),
    );
    final parsed = _parseArticleList(serverResponse);
    if (parsed.isSuccess) return parsed;

    final fallback = await fetchPopular(limit: 30);
    if (!fallback.isSuccess || fallback.data == null) return fallback;

    final query = keyword.toLowerCase();
    final filtered = fallback.data!
        .where(
          (a) => a.title.toLowerCase().contains(query),
        )
        .toList(growable: false);
    return Result.success(filtered);
  }

  Result<List<ArticleModel>> _parseArticleList(
    Result<Map<String, dynamic>> response,
  ) {
    if (!response.isSuccess || response.data == null) {
      return Result.failure(response.error ?? 'Unable to load articles.');
    }

    final data = response.data!['data'];
    if (data is! List) {
      return Result.failure('Invalid article list payload.');
    }

    final items = data
        .whereType<Map<String, dynamic>>()
        .map(ArticleModel.fromJson)
        .toList(growable: false);
    return Result.success(items);
  }
}
