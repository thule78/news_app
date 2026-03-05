class ApiEndpoints {
  static const String categories = '/categories_news';

  static String categoryArticles(int categoryId, int page) =>
      '/categories_news/$categoryId/articles?page=$page';

  static String popular(int limit) => '/articles/popular?limit=$limit';

  static String articleDetail(int id) => '/articles/$id';

  // Fallback-compatible search path; if server differs this call fails safely.
  static String search(String keyword) => '/articles/search?keyword=$keyword';
}
