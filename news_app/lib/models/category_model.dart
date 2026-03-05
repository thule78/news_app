class CategoryModel {
  const CategoryModel({
    required this.id,
    required this.name,
    required this.slug,
    required this.link,
    required this.articlesCount,
  });

  final int id;
  final String name;
  final String slug;
  final String link;
  final int articlesCount;

  factory CategoryModel.fromJson(Map<String, dynamic> json) {
    return CategoryModel(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: (json['name'] ?? '') as String,
      slug: (json['slug'] ?? '') as String,
      link: (json['link'] ?? '') as String,
      articlesCount: (json['articles_count'] as num?)?.toInt() ?? 0,
    );
  }
}
