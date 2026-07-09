import { Global, Module } from "@nestjs/common";
import { RetrievalService } from "./retrieval.service";

@Global()
@Module({
  providers: [RetrievalService],
  exports: [RetrievalService],
})
export class RetrievalModule {}
