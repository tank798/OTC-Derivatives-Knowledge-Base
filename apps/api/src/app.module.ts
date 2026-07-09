import { Module } from "@nestjs/common";
import { ConfigModule } from "@nestjs/config";
import { LlmModule } from "./modules/llm/llm.module";
import { RetrievalModule } from "./modules/retrieval/retrieval.module";
import { ComplianceModule } from "./modules/compliance/compliance.module";
import { PromptModule } from "./modules/prompt/prompt.module";

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: [".env", ".env.local"],
    }),
    PromptModule,
    LlmModule,
    RetrievalModule,
    ComplianceModule,
  ],
})
export class AppModule {}
